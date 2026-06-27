> These are my personal notes while building the **AI-Powered Customer Support Automation System using LangGraph**. The goal is to understand every concept instead of just completing the assignment.

---

# 📚 Git Notes new

---

## Remote

A **Remote** is an online Git repository connected to our local repository.

Usually the remote is named:

```
origin
```

Command:

```bash
git remote add origin <repository-url>
```

Think of a remote as the saved address of your GitHub repository.

---

## Upstream Branch

The upstream branch links a local branch with the corresponding branch on GitHub.

Example:

```bash
git push -u origin main
```

The `-u` (`--set-upstream`) option tells Git:

> "Remember that my local `main` branch is connected to GitHub's `main` branch."

After this, we only need:

```bash
git push
```

instead of

```bash
git push origin main
```

every time.


---

## Pull

Downloads the latest commits from GitHub and merges them into the local project.

```
GitHub
   │
   ▼
Laptop
```

Command:

```bash
git pull
```

Git automatically downloads only the changes that are missing from the local repository.

---


# Frequently Used Git Commands

Check project status

```bash
git status
```

Stage all files

```bash
git add .
```

Commit staged files

```bash
git commit -m "message"
```

Upload commits

```bash
git push
```

Download latest changes

```bash
git pull
```

Show commit history

```bash
git log
```

Show file differences

```bash
git diff
```

Show connected remote repository

```bash
git remote -v
```

---

# .gitignore

`.gitignore` is a file that tells Git which files or folders should **NOT** be tracked.

Example:

```gitignore
venv/
__pycache__/
memory.db
vectorstore/
```

Git simply ignores these files.

---

# Why Ignore Certain Files?

## venv/

The virtual environment contains all installed Python packages.

It may contain:

* Thousands of files
* Hundreds of megabytes of data

Instead of uploading it, we share:

```
requirements.txt
```

Anyone can recreate the environment by running:

```bash
pip install -r requirements.txt
```

---

## vectorstore/

The vector database is automatically generated during RAG.

Workflow:

```
knowledge_base/

↓

Embedding Model

↓

Vector Database

↓

vectorstore/
```

The original documents are stored inside `knowledge_base`.

The vectorstore can always be regenerated.

Therefore, it is unnecessary to upload it to GitHub.

---

## memory.db

SQLite creates this file automatically while the application runs.

It stores conversation history.

Example:

```
Customer: David

Issue: Billing

Response: Refund Pending
```

Since it changes constantly, it is usually ignored in Git.

**Exception:** For this assignment, the professor specifically asks for the SQLite database (or schema), so it will be included in the final ZIP submission.

---

## **pycache**/

Python automatically creates this folder.

It stores compiled Python bytecode (`.pyc` files) to make programs start faster.

It is regenerated automatically whenever needed.

---

# Project Folder Structure

```
CustomerSupportAI/

│

├── main.py

├── graph.py

├── state.py

├── agents.py

├── rag.py

├── memory.py

├── supervisor.py

├── human_loop.py

├── config.py

│

├── knowledge_base/

│      company_policy.txt

│      pricing_guide.txt

│      technical_manual.txt

│      faq.txt

│

├── vectorstore/

│

├── screenshots/

│

├── memory.db

├── README.md

├── requirements.txt

├── workflow.png

└── developer.md
```

---

# Current Understanding

* Git manages project history locally.
* GitHub stores Git repositories online.
* Git tracks changes using commits.
* A commit is a checkpoint.
* A remote is the connection between the local repository and GitHub.
* An upstream branch links the local branch with the corresponding remote branch.
* `.gitignore` prevents unnecessary files from being tracked.
* `vectorstore/` is automatically generated from the knowledge base.
* `memory.db` stores SQLite conversation history.
* `venv/` stores installed Python packages and should not be uploaded.
* `requirements.txt` is used to recreate the Python environment.

---

# Things to Learn Next

* Python Virtual Environment (venv)
* pip
* requirements.txt
* LangChain
* LangGraph
* State
* Nodes
* Edges
* Conditional Routing
* RAG
* Vector Databases
* Embeddings
* SQLite Memory
* Human-in-the-Loop
* Supervisor Agent
* Multi-Agent Systems

--------------------------------------------------------------------------------------------

## Virtual Environment (venv)

A virtual environment (venv) is an isolated Python environment created for a specific project. It keeps the project's Python packages and dependencies separate from other Python projects on the same computer.

Without a virtual environment, all Python packages would be installed globally. This can lead to dependency conflicts when different projects require different versions of the same library.

Each project should have its own virtual environment.

### Why use a virtual environment?

* Prevents dependency conflicts between projects.
* Keeps project-specific packages isolated.
* Makes projects easier to share and reproduce.
* Prevents unnecessary packages from being installed globally.

### Contents of a virtual environment

A typical `venv` folder contains:

* `Scripts/` – Python executable and activation scripts (Windows).
* `Lib/` – Installed Python packages.
* `Include/` – Header files used by some packages.
* `pyvenv.cfg` – Configuration file for the virtual environment.

### Activating a virtual environment

On Windows (Git Bash):

```bash
source venv/Scripts/activate
```

On Windows (Command Prompt):

```cmd
venv\Scripts\activate
```

On PowerShell:

```powershell
venv\Scripts\Activate.ps1
```

### Deactivating a virtual environment

```bash
deactivate
```

### Why is `venv` added to `.gitignore`?

The `venv` folder can contain thousands of installed files and may occupy hundreds of megabytes. Instead of uploading it to GitHub, developers share a `requirements.txt` file. Anyone cloning the project can recreate the same environment using:

```bash
pip install -r requirements.txt
```


--------------------------------------------------------------------------------------------

# CustomerSupportAI - Agentic AI Project Documentation

## Project Overview

CustomerSupportAI is an Agentic AI based customer support assistant built using LangGraph and LangChain.

The system demonstrates the core concepts of Agentic AI:

- Autonomous reasoning
- Tool usage
- Retrieval Augmented Generation (RAG)
- Persistent memory
- Human-in-the-loop approval


---

# Technology Stack

## Programming Language

Python 3.12.10


## Agent Framework

LangGraph

Purpose:
- Build stateful AI agent workflows
- Define agent nodes and transitions
- Manage decision making flow


## LLM Runtime

Ollama

Purpose:
- Run Large Language Models locally
- Provide the reasoning engine for the AI agent
- Avoid dependency on external API keys


Planned Model:

Llama 3.1 8B


## LangChain

Purpose:
- Connect the LLM with tools
- Handle prompts
- Manage AI components


## Vector Database

ChromaDB

Purpose:
- Store document embeddings
- Enable semantic search for RAG


## Memory Database

SQLite

Purpose:
- Store conversation history
- Maintain user context between interactions


---

# System Architecture


User
 |
 v
Agent Interface
 |
 v
LangGraph Workflow
 |
 |
 +----------------+
 |                |
 v                v
LLM Reasoning    Tools

 |
 v

Ollama Local Model


Additional Components:

RAG:
Documents → Embeddings → Vector Store → Retrieved Context


Memory:

Conversation → SQLite Database


---

# Development Progress

## Completed

- Installed Python 3.12.10
- Created project repository
- Created virtual environment


## In Progress

- Installing LangGraph
- Setting up LangChain environment


## Pending

- Install Ollama
- Download Llama model
- Implement agent workflow
- Add tools
- Add RAG pipeline
- Add SQLite memory
- Add Human-in-the-loop approval
- Create final documentation


---

# Environment Setup

Python Version:

Python 3.12.10


Virtual Environment:

venv/


Activation:

Windows Git Bash:

source venv/Scripts/activate


---

# Installation Commands

Initial dependencies:

pip install langgraph


Upcoming:

pip install langchain langchain-community langchain-ollama chromadb python-dotenv


---

# Agent Workflow Design

The agent will contain:

1. User Input Node

Receives user queries.


2. Reasoning Node

Uses the LLM to decide actions.


3. Tool Node

Executes required functions.


4. Retrieval Node

Searches documents using RAG.


5. Memory Node

Stores and retrieves previous conversations.


6. Human Approval Node

Requests human confirmation for sensitive actions.


---

# Project Goal

Build a functional Agentic AI customer support assistant demonstrating modern AI engineering concepts including autonomous workflows, tool calling, memory management and knowledge retrieval.



## Completed :
   - Installed Python 3.12.10
- Created virtual environment (venv)
- Upgraded pip
- Installed LangGraph

## Progress :
- Installing LangChain ecosystem dependencies
- Setting up Ollama local LLM runtime

