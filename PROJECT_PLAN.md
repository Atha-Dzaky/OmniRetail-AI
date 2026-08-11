# OmniRetail AI - Comprehensive Project Plan

## 📋 Executive Summary

**Project:** OmniRetail AI  
**Type:** Agentic E-commerce Data Analysis Chatbot  
**Framework:** LangChain + LangGraph  
**Timeline:** 4 Phases (8-12 weeks)  
**Target:** AI Engineering Bootcamp Final Project  

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "User Interface Layer"
        UI[Streamlit/FastAPI Frontend]
    end
    
    subgraph "LangGraph Orchestration Layer"
        Router[Router Node]
        SQLAgent[SQL Agent Node]
        PythonAgent[Python Analysis Agent]
        OutputFormatter[Output Formatter Node]
        
        Router --> SQLAgent
        Router --> PythonAgent
        SQLAgent --> PythonAgent
        PythonAgent --> OutputFormatter
    end
    
    subgraph "Data Layer"
        PostgresDB[(PostgreSQL Database)]
        FileSystem[Chart Generation Storage]
    end
    
    subgraph "External Services"
        GroqAPI[Groq/OpenAI LLM API]
        LangSmith[LangSmith Tracking]
    end
    
    UI --> Router
    SQLAgent --> PostgresDB
    PythonAgent --> FileSystem
    Router -.-> LangSmith
    SQLAgent -.-> LangSmith
    PythonAgent -.-> LangSmith
    Router -.-> GroqAPI
    SQLAgent -.-> GroqAPI
    PythonAgent -.-> GroqAPI
```

### LangGraph Workflow Design

```python
# Core LangGraph State Schema
class OmniRetailState(TypedDict):
    user_query: str
    intent: str  # "sql_query", "data_analysis", "mixed"
    sql_query: str
    sql_results: List[Dict]
    analysis_code: str
    analysis_results: Dict
    charts: List[str]  # file paths
    final_response: str
    error_messages: List[str]
```

#### Node Definitions:

1. **Router Node**
   - Analyzes user intent
   - Routes to SQL Agent, Python Agent, or both
   - Handles conversation context

2. **SQL Agent Node**
   - Converts natural language to SQL
   - Executes queries against PostgreSQL
   - Validates and sanitizes results

3. **Python Agent Node**
   - Performs data analysis on SQL results
   - Generates visualizations (matplotlib/plotly)
   - Calculates metrics and insights

4. **Output Formatter Node**
   - Combines SQL results + analysis + charts
   - Formats final user response
   - Handles error states gracefully

---

## 🗄️ Database Schema Design

### Proposed PostgreSQL Schema

```sql
-- Core product catalog
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    design_no VARCHAR(100),
    category VARCHAR(100),
    size VARCHAR(50),
    color VARCHAR(50),
    stock_quantity INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sales transactions (Amazon + International)
CREATE TABLE sales_transactions (
    transaction_id SERIAL PRIMARY KEY,
    order_date DATE NOT NULL,
    sku VARCHAR(100) REFERENCES products(sku),
    platform VARCHAR(50), -- 'Amazon', 'International', etc.
    customer_type VARCHAR(20), -- 'B2B', 'B2C'
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'INR',
    region VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Platform pricing (P&L data)
CREATE TABLE platform_pricing (
    pricing_id SERIAL PRIMARY KEY,
    sku VARCHAR(100) REFERENCES products(sku),
    platform VARCHAR(50), -- 'Amazon', 'Flipkart', 'Myntra', 'TP1', 'TP2'
    mrp DECIMAL(10,2),
    selling_price DECIMAL(10,2),
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Expenses and logistics
CREATE TABLE expenses (
    expense_id SERIAL PRIMARY KEY,
    expense_type VARCHAR(100), -- 'Shipping', 'Storage', 'Marketing', etc.
    expense_category VARCHAR(50), -- 'IIGF', 'Shiprocket', 'INCREFF'
    amount DECIMAL(10,2),
    expense_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Warehouse operations
CREATE TABLE warehouse_operations (
    operation_id SERIAL PRIMARY KEY,
    warehouse_type VARCHAR(50), -- 'Cloud', 'Traditional'
    provider VARCHAR(50), -- 'Shiprocket', 'INCREFF'
    cost_per_unit DECIMAL(10,2),
    efficiency_rating DECIMAL(3,2),
    operation_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for query performance
CREATE INDEX idx_sales_date ON sales_transactions(order_date);
CREATE INDEX idx_sales_sku ON sales_transactions(sku);
CREATE INDEX idx_sales_platform ON sales_transactions(platform);
CREATE INDEX idx_pricing_sku ON platform_pricing(sku);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
```

### Data Loading Strategy

```python
# CSV to PostgreSQL mapping
CSV_MAPPINGS = {
    'Amazon Sale Report.csv': 'sales_transactions',
    'International sale Report.csv': 'sales_transactions', 
    'Sale Report.csv': 'products',
    'P & L March 2021.csv': 'platform_pricing',
    'May-2022.csv': 'platform_pricing',
    'Expense IIGF.csv': 'expenses',
    'Cloud Warehouse Compersion Chart.csv': 'warehouse_operations'
}
```

---

## 🛠️ Tech Stack & Dependencies

### Core Framework
```python
# requirements.txt
langchain==0.1.0
langgraph==0.0.40
langchain-experimental==0.0.50
langsmith==0.0.80

# Database & ORM
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1

# Data Processing
pandas==2.1.4
numpy==1.26.2
python-dateutil==2.8.2

# Visualization
matplotlib==3.8.2
plotly==5.17.0
seaborn==0.13.0

# API & UI
fastapi==0.104.1
streamlit==1.29.0
uvicorn==0.24.0

# LLM APIs
openai==1.6.1
groq==0.4.1

# Environment & Deployment
python-dotenv==1.0.0
docker==6.1.3
pydantic==2.5.2
pydantic-settings==2.1.0

# Development & Testing
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0
```

### Infrastructure Components
```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: omniretail
      POSTGRES_USER: omniretail
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql://omniretail:${DB_PASSWORD}@postgres:5432/omniretail
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
      - GROQ_API_KEY=${GROQ_API_KEY}

volumes:
  postgres_data:
```

---

## 📈 Development Roadmap (4 Phases)

### Phase 1: Foundation & Data Pipeline (Weeks 1-2)

**Objective:** Establish core infrastructure and data ingestion

#### Tasks:
- [ ] **1.1** Set up PostgreSQL database with schema
- [ ] **1.2** Create data cleaning pipeline for CSV files
- [ ] **1.3** Implement ETL process with date format standardization
- [ ] **1.4** Set up Docker environment with docker-compose
- [ ] **1.5** Configure LangSmith project and API keys
- [ ] **1.6** Create basic FastAPI application structure

**Deliverables:**
- Working PostgreSQL database with sample data
- Docker containerized environment
- Data validation and cleaning scripts
- Basic API endpoints for data access

**Verification:**
- All CSV files successfully loaded to PostgreSQL
- Docker containers start without errors
- LangSmith tracking captures basic API calls
- Database queries return expected results

---

### Phase 2: Core Agent Development (Weeks 3-5)

**Objective:** Build SQL and Python agents with LangGraph orchestration

#### Tasks:
- [ ] **2.1** Implement SQL Agent with natural language to SQL conversion
- [ ] **2.2** Create Python Agent for data analysis and visualization
- [ ] **2.3** Design LangGraph state management and workflow
- [ ] **2.4** Build Router Node for intent classification
- [ ] **2.5** Implement error handling and recovery mechanisms
- [ ] **2.6** Create comprehensive test suite for agents

**Deliverables:**
- Functional SQL Agent (95%+ query accuracy)
- Python Agent generating charts and insights
- LangGraph workflow orchestration
- Agent testing framework

**Verification:**
- SQL Agent handles complex multi-table queries
- Python Agent generates meaningful visualizations
- LangGraph state transitions work correctly
- All agents properly tracked in LangSmith

---

### Phase 3: LLMOps Integration & User Interface (Weeks 6-8)

**Objective:** Complete LangSmith integration and build user-friendly interface

#### Tasks:
- [ ] **3.1** Implement comprehensive LangSmith tracking for all LLM calls
- [ ] **3.2** Build Streamlit chatbot interface
- [ ] **3.3** Add conversation memory and context management
- [ ] **3.4** Implement cost tracking and usage analytics
- [ ] **3.5** Create performance monitoring dashboard
- [ ] **3.6** Add export functionality for reports and charts

**Deliverables:**
- Complete Streamlit chatbot application
- LangSmith dashboard with cost/latency metrics
- Conversation persistence and context
- Export capabilities (PDF, CSV, PNG)

**Verification:**
- Chatbot handles multi-turn conversations
- LangSmith captures 100% of LLM interactions
- Cost tracking shows accurate token usage
- Export features work for all data types

---

### Phase 4: Deployment & Production Readiness (Weeks 9-12)

**Objective:** Deploy to homelab and ensure production readiness

#### Tasks:
- [ ] **4.1** Optimize Docker images for production
- [ ] **4.2** Set up reverse proxy (Nginx) and SSL certificates
- [ ] **4.3** Implement logging and monitoring (Prometheus/Grafana)
- [ ] **4.4** Create backup and disaster recovery procedures
- [ ] **4.5** Performance testing and optimization
- [ ] **4.6** Create comprehensive documentation and demo

**Deliverables:**
- Production-ready deployment on homelab
- Monitoring and alerting system
- Complete project documentation
- Demo video and presentation

**Verification:**
- Application handles concurrent users
- Monitoring shows system health metrics
- Backup procedures tested and verified
- Performance meets bootcamp requirements

---

## 🧪 Example User Interactions

### Sample Queries the System Should Handle:

1. **Simple SQL Query:**
   - User: "What were our top 5 products by sales last month?"
   - System: Generates SQL → Executes → Returns formatted results

2. **Complex Analysis:**
   - User: "Compare Amazon vs International sales performance and show me the profit margin analysis"
   - System: Multi-query → Data analysis → Generates comparative charts

3. **Business Intelligence:**
   - User: "Which warehouse provider is most cost-effective for our operations?"
   - System: Complex joins → Statistical analysis → Recommendation with visualization

---

## 📊 Success Metrics & KPIs

### Technical Performance:
- **Query Accuracy:** >95% correct SQL generation
- **Response Time:** <30 seconds for complex queries
- **Uptime:** >99% availability
- **LangSmith Coverage:** 100% LLM call tracking

### Business Value:
- **User Engagement:** Multi-turn conversation capability
- **Data Coverage:** Support for all 7 CSV data sources
- **Insight Quality:** Actionable business recommendations
- **Cost Efficiency:** <$5/month in LLM API costs

---

## 🚀 Getting Started Checklist

### Pre-Development Setup:
- [ ] Clone repository and set up virtual environment
- [ ] Obtain API keys (Groq/OpenAI, LangSmith)
- [ ] Configure homelab environment (Ubuntu VM, Docker)
- [ ] Download and validate e-commerce dataset
- [ ] Set up development database locally

### Phase 1 Quick Start:
```bash
# 1. Environment setup
python -m venv omniretail-env
source omniretail-env/bin/activate  # Windows: omniretail-env\Scripts\activate
pip install -r requirements.txt

# 2. Database setup
docker-compose up -d postgres
python scripts/setup_database.py

# 3. Data loading
python scripts/load_csv_data.py --validate

# 4. Basic API test
uvicorn app.main:app --reload
curl http://localhost:8000/health
```

---

## 🔧 Development Guidelines

### Code Standards:
- Follow PEP 8 with Black formatting
- Type hints for all function signatures
- Comprehensive docstrings and comments
- 90%+ test coverage requirement

### LangSmith Integration:
- Every LLM call must be traced
- Include custom metadata (query_type, complexity)
- Set up cost alerts for budget management
- Weekly performance review sessions

### Security Considerations:
- SQL injection prevention in all queries
- Input sanitization for user queries
- Environment variable management
- Rate limiting for API endpoints

---

This comprehensive plan provides a solid foundation for your OmniRetail AI project. The architecture leverages LangGraph's agentic capabilities while meeting all bootcamp requirements. Each phase builds incrementally toward a production-ready system that demonstrates advanced RAG techniques and proper LLMOps practices.

Ready to start with Phase 1? I can help you implement any specific component or provide more detailed technical specifications for particular areas.