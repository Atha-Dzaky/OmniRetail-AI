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
            "You are an expert SQL query generator. Given the schema below and the user request, output ONLY the raw SQL statement. "
            "CRITICAL: You must ONLY output the raw SQL query. Do not include any conversational text, explanations, or the word 'Question'. "
            "Do not include any prefix or suffix, including 'SQLQuery:', 'SQLResult:', or 'Answer:'.\n\n"
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


def _ensure_chart_dir() -> Path:
    chart_dir = Path(__file__).resolve().parent.parent / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    return chart_dir


def create_omniretail_graph() -> StateGraph[OmniRetailState, None, OmniRetailState, OmniRetailState]:
    llm = _create_llm()
    sql_agent = _create_sql_agent(llm)
    python_code_generator = _create_python_code_generator(llm)
    chart_dir = _ensure_chart_dir()

    graph = StateGraph(state_schema=OmniRetailState)

    def sql_node(state: OmniRetailState) -> OmniRetailState:
        query = state["user_query"]
        result_response = sql_agent.invoke({"query": query})
        raw_sql_output = str(result_response.get("result", result_response))
        sql_query = _extract_sql_query(raw_sql_output)
        sql_result = _execute_sql_query(sql_query)

        return {
            "sql_result": sql_result,
            "final_response": sql_result,
        }

    def python_node(state: OmniRetailState) -> OmniRetailState:
        sql_result = state["sql_result"]
        chart_path = chart_dir / f"omniretail_chart_{uuid4().hex}.png"
        
        python_prompt = (
            "You are a Python data analyst. Generate ONLY Python code to create a chart from the SQL result below. "
            "CRITICAL: You must ONLY output raw Python code wrapped in ```python``` blocks. "
            "Do not include any explanatory text, comments, or conversation outside the code block.\n\n"
            "Requirements:\n"
            "1. Parse the sql_result (JSON string) using json.loads()\n"
            "2. Create a meaningful chart using matplotlib\n"
            "3. Save the chart to chart_path using plt.savefig()\n"
            "4. Use plt.close() after saving\n\n"
            f"Variables available:\n"
            f"- sql_result = {sql_result!r}\n"
            f"- chart_path = {str(chart_path)!r}\n\n"
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
            execution_result = _execute_python_code(python_code, str(chart_path), sql_result)
            
            if execution_result.get("success"):
                return {
                    "python_code": python_code,
                    "chart_path": str(chart_path),
                    "final_response": execution_result["message"],
                }
            else:
                return {
                    "python_code": f"Error: {execution_result.get('error', 'Unknown error')}",
                    "chart_path": str(chart_path),
                    "final_response": f"Python execution failed: {execution_result.get('error', 'Unknown error')}",
                }
                
        except Exception as e:
            return {
                "python_code": f"Error extracting or executing code: {str(e)}",
                "chart_path": str(chart_path),
                "final_response": f"Python node failed: {str(e)}",
            }

    graph.add_node("SQLAgent", sql_node)
    graph.add_node("PythonAgent", python_node)
    graph.set_entry_point("SQLAgent")
    graph.add_edge("SQLAgent", "PythonAgent")
    graph.set_finish_point("PythonAgent")

    return graph
