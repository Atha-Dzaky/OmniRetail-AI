from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from typing_extensions import TypedDict
from uuid import uuid4

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import PromptTemplate
from langchain_experimental.sql.base import SQLDatabaseChain
from langchain_experimental.tools import PythonREPLTool
from langchain_groq.chat_models import ChatGroq
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from sqlalchemy import text

from app.db import DATABASE_URL, engine


class OmniRetailState(TypedDict):
    user_query: str
    sql_result: str
    python_code: str
    chart_path: str
    final_response: str


def _create_llm() -> BaseLanguageModel:
    return ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY"),
    )


def _create_sql_agent(llm: BaseLanguageModel) -> SQLDatabaseChain:
    sql_db = SQLDatabase.from_uri(DATABASE_URL)
    sql_prompt = PromptTemplate(
        input_variables=["input", "table_info", "dialect", "top_k"],
        template=(
            "You are an expert SQL query generator for an e-commerce database. Given the schema below and the user request, output ONLY the raw SQL statement.\n\n"
            "=== CRITICAL SQL RULES ===\n"
            "1. You must ONLY output the raw SQL query. Do not include any conversational text, explanations, or the word 'Question'.\n"
            "2. Do not include any prefix or suffix, including 'SQLQuery:', 'SQLResult:', or 'Answer:'.\n"
            "3. AGGREGATE FUNCTIONS: If you use aggregate functions like SUM(), COUNT(), AVG(), MIN(), or MAX(), ALL other columns in the SELECT clause MUST be included in the GROUP BY clause.\n"
            "4. SCHEMA AWARENESS: The 'size' and 'color' columns are ONLY in the 'products' table. If a query asks about size/color and sales, you MUST JOIN 'sales_transactions' with 'products'.\n"
            "5. DATA EXISTENCE: If the user asks about data that does not exist in the database (e.g., cats, food, weather, animals, sports, etc. - anything unrelated to e-commerce sales), DO NOT generate SQL. Return EXACTLY: 'MAAF_DATA_TIDAK_ADA'\n"
            "6. AMBIGUOUS COLUMNS IN JOINS: When performing a JOIN between tables that have the same column name (e.g., 'sku' exists in both 'products' and 'sales_transactions'), you MUST use table aliases or full table names in the SELECT clause (e.g., 'SELECT p.sku, p.size' instead of just 'SELECT sku').\n"
            "7. PERCENTAGE & DISTRIBUTION CALCULATIONS: When asked to calculate percentages or distributions, use Window Functions or Subqueries. Example: Calculate the total sum first, then divide each group's sum by the total, then multiply by 100.\n\n"
            "Schema:\n{table_info}\n"
            "Dialect: {dialect}\n"
            "Limit results to at most {top_k} rows unless the user explicitly asks for more.\n\n"
            "Request and query marker:\n{input}"
        ),
    )
    return SQLDatabaseChain.from_llm(
        llm,
        sql_db,
        prompt=sql_prompt,
        return_sql=True,
        return_direct=True,
    )

def _extract_sql_query(text_output: str) -> str:
    sql_output = text_output.strip()
    pattern = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP)\b[\s\S]*?(?:;|$)",
        re.IGNORECASE,
    )
    match = pattern.search(sql_output)
    if not match:
        raise ValueError(
            "Unable to extract a valid SQL query from the model output."
        )
    return match.group(0).strip()


def _execute_sql_query(sql_query: str) -> str:
    with engine.begin() as conn:
        result = conn.execute(text(sql_query))
        try:
            rows = result.mappings().all()
            formatted = [dict(row) for row in rows]
        except Exception:
            rows = result.all()
            formatted = [tuple(row) if isinstance(row, tuple) else row for row in rows]
    return json.dumps(formatted, default=str, ensure_ascii=False)


def _create_python_code_generator(llm: BaseLanguageModel) -> BaseLanguageModel:
    return llm


def _extract_python_code(text_output: str) -> str:
    """Extract Python code from LLM output wrapped in ```python``` blocks."""
    pattern = re.compile(r"```python\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text_output)
    if not match:
        raise ValueError(
            "Unable to extract Python code from the model output. "
            "Expected code wrapped in ```python``` blocks."
        )
    return match.group(1).strip()


def _execute_python_code(python_code: str, chart_path: str, sql_result: str) -> dict:
    """Execute Python code in a safe namespace with predefined variables."""
    namespace = {
        "chart_path": chart_path,
        "sql_result": sql_result,
        "json": json,
        "os": os,
        "re": re,
        "Path": Path,
    }
    
    # Import common data science libraries
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        import numpy as np
        namespace.update({"pd": pd, "plt": plt, "np": np})
    except ImportError as e:
        return {"error": f"Required library not available: {e}"}
    
    try:
        exec(python_code, namespace)
        return {
            "success": True,
            "message": f"Python code executed successfully. Chart saved to: {chart_path}",
        }
    except Exception as e:
        return {"error": f"Python execution failed: {str(e)}"}


def _get_chart_dir() -> str:
    """Return the container-aware chart directory path."""
    # Use /app/charts inside Docker, fall back to local for dev
    if os.path.exists("/app/charts"):
        return "/app/charts"
    else:
        chart_dir = Path(__file__).resolve().parent.parent / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        return str(chart_dir)

def _is_empty_or_invalid_result(sql_result: str) -> bool:
    """Check if sql_result is empty, None, or contains error marker."""
    if not sql_result or sql_result is None:
        return True
    if "MAAF_DATA_TIDAK_ADA" in sql_result:
        return True
    try:
        parsed = json.loads(sql_result)
        if isinstance(parsed, list) and len(parsed) == 0:
            return True
    except (json.JSONDecodeError, TypeError):
        pass
    return False


def create_omniretail_graph() -> StateGraph[OmniRetailState, None, OmniRetailState, OmniRetailState]:
    llm = _create_llm()
    sql_agent = _create_sql_agent(llm)
    python_code_generator = _create_python_code_generator(llm)
    chart_base_dir = _get_chart_dir()

    graph = StateGraph(state_schema=OmniRetailState)

    def sql_node(state: OmniRetailState) -> OmniRetailState:
        query = state["user_query"]
        try:
            result_response = sql_agent.invoke({"query": query})
            raw_sql_output = str(result_response.get("result", result_response))
            
            # Check for refusal marker
            if "MAAF_DATA_TIDAK_ADA" in raw_sql_output:
                return {
                    "sql_result": "MAAF_DATA_TIDAK_ADA",
                    "final_response": "Maaf, saya tidak dapat menemukan data atau membuat query untuk pertanyaan tersebut. Silakan tanyakan hal lain seputar data e-commerce.",
                    "python_code": "",
                    "chart_path": "",
                }
            
            sql_query = _extract_sql_query(raw_sql_output)
            sql_result = _execute_sql_query(sql_query)

            return {
                "sql_result": sql_result,
                "final_response": sql_result,
            }
        except ValueError as e:
            # SQL extraction or execution failed
            return {
                "sql_result": "",
                "final_response": "Maaf, saya tidak dapat menemukan data atau membuat query untuk pertanyaan tersebut. Silakan tanyakan hal lain seputar data e-commerce.",
                "python_code": "",
                "chart_path": "",
            }
        except Exception as e:
            # Any other unexpected error
            return {
                "sql_result": "",
                "final_response": "Maaf, saya tidak dapat menemukan data atau membuat query untuk pertanyaan tersebut. Silakan tanyakan hal lain seputar data e-commerce.",
                "python_code": "",
                "chart_path": "",
            }

    def python_node(state: OmniRetailState) -> OmniRetailState:
        sql_result = state["sql_result"]
        
        # Check if result is empty or invalid
        if _is_empty_or_invalid_result(sql_result):
            return {
                "python_code": "",
                "chart_path": "",
                "final_response": "Maaf, saya tidak dapat menemukan data terkait pertanyaan Anda di database. Silakan coba pertanyaan lain seputar penjualan e-commerce.",
            }
        
        filename = f"omniretail_chart_{uuid4().hex}.png"
        chart_path_absolute = os.path.join(chart_base_dir, filename)
        chart_url = f"/charts/{filename}"
        
        python_prompt = (
            "You are a Python data analyst. Generate ONLY Python code to create a chart from the SQL result below. "
            "CRITICAL: You must ONLY output raw Python code wrapped in ```python``` blocks. "
            "Do not include any explanatory text, comments, or conversation outside the code block.\n\n"
            "Requirements:\n"
            "1. Parse the sql_result (JSON string) using json.loads()\n"
            "2. Create a meaningful chart using matplotlib\n"
            "3. Save the chart EXACTLY to the chart_path variable using plt.savefig(chart_path)\n"
            "4. Use plt.close() after saving\n"
            "5. DO NOT modify the chart_path variable - use it exactly as provided\n"
            "6. CRITICAL VISUALIZATION: You MUST strictly follow the user's requested chart type. "
            "If the user asks for a 'pie chart', you MUST use plt.pie(). "
            "If they ask for a 'line chart', you MUST use plt.plot(). "
            "If they ask for a 'bar chart' or no type specified, use plt.bar(). "
            "Do not default to bar charts if a specific chart type is requested.\n\n"
            f"Variables available (use these exactly):\n"
            f"- sql_result = {sql_result!r}\n"
            f"- chart_path = {chart_path_absolute!r}\n\n"
            "Example format:\n"
            "```python\n"
            "import json\n"
            "import matplotlib.pyplot as plt\n"
            "data = json.loads(sql_result)\n"
            "# your chart code here\n"
            "plt.savefig(chart_path)\n"
            "plt.close()\n"
            "```"
        )
        
        try:
            llm_response = python_code_generator.invoke(python_prompt)
            llm_output = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            
            python_code = _extract_python_code(llm_output)
            execution_result = _execute_python_code(python_code, chart_path_absolute, sql_result)
            
            if execution_result.get("success"):
                return {
                    "python_code": python_code,
                    "chart_path": chart_url,
                    "final_response": f"Chart generated successfully. Available at: {chart_url}",
                }
            else:
                return {
                    "python_code": f"Error: {execution_result.get('error', 'Unknown error')}",
                    "chart_path": "",
                    "final_response": f"Python execution failed: {execution_result.get('error', 'Unknown error')}",
                }
                
        except Exception as e:
            return {
                "python_code": f"Error extracting or executing code: {str(e)}",
                "chart_path": "",
                "final_response": f"Python node failed: {str(e)}",
            }

    graph.add_node("SQLAgent", sql_node)
    graph.add_node("PythonAgent", python_node)
    graph.set_entry_point("SQLAgent")
    graph.add_edge("SQLAgent", "PythonAgent")
    graph.set_finish_point("PythonAgent")

    return graph
