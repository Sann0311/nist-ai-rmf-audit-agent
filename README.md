# NIST AI RMF Audit Agent

> An AI-powered audit agent for conducting security posture assessments based on the **NIST AI Risk Management Framework (AI RMF)**

[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red?logo=streamlit)](https://streamlit.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-teal?logo=fastapi)](https://fastapi.tiangolo.com)

## Features

- **Interactive Chat Interface** - Guided audit conversations using Streamlit
- **7 NIST AI RMF Categories** - Complete coverage of trustworthy AI characteristics
- **Excel-Based Audit Data** - 234 structured audit questions with baseline evidence
- **Progress Tracking** - Real-time audit progress with visual indicators
- **Evidence Evaluation** - Automated conformity assessment (Full/Partial/No)
- **Session Management** - Persistent audit sessions with state management
- **Docker Containerized** - Easy deployment with docker-compose

This is an AI-powered audit agent designed to conduct security posture assessments based on the **NIST AI Risk Management Framework (AI RMF)**. The system guides users through structured audits of the 7 NIST AI RMF trustworthy characteristics.

##  Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │     Agent       │
│  (Streamlit)    │◄──►│   (FastAPI)     │◄──►│  (Google ADK)   │
│   Port 8501     │    │   Port 8001     │    │   Port 8000     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                               ┌─────────────────┐
                                               │   Audit Data    │
                                               │  (Audit.xlsx)   │
                                               └─────────────────┘
```

The system consists of three main components:

### 1. **Agent Service** (Port 8000)

- Built with Google ADK (Agent Development Kit)
- Contains the core audit logic and NIST AI RMF knowledge
- Processes Excel-based audit questions and baseline evidence
- Evaluates user responses and evidence for conformity

### 2. **Backend API** (Port 8001)

- FastAPI service that acts as a bridge between frontend and agent
- Handles session management and API routing
- Processes audit context and forwards requests to the agent

### 3. **Frontend Interface** (Port 8501)

- Streamlit-based interactive chat interface
- Provides category selection and guided audit workflow
- Real-time progress tracking and audit session management

## NIST AI RMF Categories

The system audits against 7 trustworthy AI characteristics:

1. **Privacy-Enhanced** - Data protection and privacy measures
2. **Valid & Reliable** - Model accuracy and performance validation
3. **Safe** - Safety measures and risk mitigation
4. **Secure & Resilient** - Security controls and resilience
5. **Accountable & Transparent** - Governance and transparency
6. **Explainable and Interpretable** - Model interpretability
7. **Fair – With Harmful Bias Managed** - Bias mitigation and fairness

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Ollama running locally (for LLM inference)
- Python 3.10+ (for development)

### Quick Start

1. **Clone and navigate to the project:**

   ```bash
   cd agent_skeleton
   ```

2. **Ensure Ollama is running with a compatible model:**

   ```bash
   ollama pull llama3.2:3b
   ollama serve
   ```

3. **Build and start all services:**


   # On Linux/Mac:
   ./start_audit_agent.sh

   # Or manually with Docker Compose:
   cd agent_skeleton
   docker-compose up --build
   ```

4. **Access the frontend:**
   Open your browser to: `http://localhost:8501`

### Service URLs

- **Frontend (Streamlit):** http://localhost:8501
- **Backend API:** http://localhost:8001
- **Agent Service:** http://localhost:8000
- **API Documentation:** http://localhost:8001/docs

## Audit Workflow

### 1. Category Selection

- Choose one of the 7 NIST AI RMF categories to audit
- Each category contains multiple main questions with sub-questions

### 2. Question & Answer Process

For each question in the selected category:

**a. Question Presentation**

- Main question from NIST AI RMF framework
- Associated NIST control reference (e.g., MEASURE 2.10)

**b. Observation Recording**

- User provides their answer/observation
- Response is recorded in the audit trail

**c. Baseline Evidence Review**

- System presents expected baseline evidence
- Detailed requirements for documentation and proof

**d. Evidence Submission**

- User provides evidence matching baseline requirements
- Can include documents, screenshots, policies, etc.

**e. Conformity Evaluation**

- System evaluates evidence against baseline
- Returns one of three conformity levels:
  - **Full Conformity** - Evidence fully meets requirements
  - **Partial Conformity** - Evidence partially meets requirements
  - **No Conformity** - Evidence does not meet requirements

### 3. Progress Tracking

- Real-time progress indicators
- Session management across multiple questions
- Audit trail maintenance

## Data Structure

### Audit.xlsx Structure

The system uses an Excel file containing:

- **Question** - Main audit questions
- **NIST AI RMF Control** - Associated control references
- **Trust-worthiness characteristic** - Category classification
- **Sub Question** - Detailed sub-questions
- **Baseline Evidence** - Expected evidence requirements

### Session Management

Each audit session tracks:

- Selected category
- Current question index
- User observations
- Evidence evaluations
- Conformity assessments

## Development

### Local Development Setup

1. **Install Python dependencies:**

   ```bash
   pip install pandas openpyxl streamlit fastapi uvicorn httpx python-multipart
   ```

2. **Run components individually:**

   **Backend:**

   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

   **Frontend:**

   ```bash
   streamlit run frontend_streamlit.py --server.port 8501
   ```

### File Structure

```
agent_skeleton/
├── agent/
│   ├── multi_tool_agent/
│   │   ├── agent.py          # Main agent configuration
│   │   ├── tool.py           # Audit tool implementation
│   │   └── app/
│   │       └── Audit.xlsx    # NIST AI RMF audit questions
│   └── tool.dockerfile       # Agent container setup
├── backend/
│   ├── main.py              # FastAPI backend
│   └── backend.dockerfile   # Backend container setup
├── frontend_streamlit.py    # Streamlit frontend
├── docker-compose.yml      # Service orchestration
└── Audit.xlsx             # Source audit data
```

## 🛠Customization

### Adding New Categories

1. Update the Excel file with new category data
2. Modify `get_nist_categories()` in `tool.py`
3. Update frontend category list

### Modifying Evaluation Logic

- Update `evaluate_evidence()` method in `AuditSession` class
- Customize conformity assessment criteria
- Add additional evaluation metrics

### Extending API Endpoints

- Add new endpoints in `backend/main.py`
- Implement corresponding frontend features
- Update agent tool capabilities

## API Reference

### Backend Endpoints

- `GET /api/status` - Health check
- `POST /api/run` - Execute agent commands
- `GET /api/audit/categories` - Get available categories
- `POST /api/audit/start` - Start new audit session

### Agent Tool Actions

- `get_categories` - List available audit categories
- `start_session` - Initialize audit for category
- `get_current_question` - Retrieve current question
- `submit_answer` - Submit observation
- `submit_evidence` - Submit evidence for evaluation

## Security Considerations

- All audit data is processed locally
- No external API calls for sensitive information
- Session isolation and data protection
- Configurable retention policies

## Compliance Features

- NIST AI RMF alignment
- Audit trail generation
- Evidence documentation
- Conformity assessment reports
- Progress tracking and reporting

## Troubleshooting

### Common Issues

1. **Ollama Connection Error:**

   - Ensure Ollama is running on localhost:11434
   - Check model availability: `ollama list`

2. **Excel File Not Found:**

   - Verify Audit.xlsx is in the correct location
   - Check Docker volume mounting

3. **Frontend Connection Error:**
   - Ensure backend is running on port 8001
   - Check network connectivity between containers

### Logs and Debugging

- View container logs: `docker-compose logs [service_name]`
- Monitor API calls in backend logs
- Check Streamlit console for frontend issues

