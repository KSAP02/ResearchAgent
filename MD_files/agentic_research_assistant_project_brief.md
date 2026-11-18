# Agentic Research & Analysis Assistant

*A one-day LangGraph project to demonstrate agent orchestration, tool
use, state management, retrieval, and conditional workflows.*

------------------------------------------------------------------------

## 1. Project overview

Build an AI-powered research assistant that takes a technical question,
searches for relevant academic papers, retrieves supporting information,
compares findings, checks whether claims are supported by evidence, and
produces a cited research report.

**Example user query:**

> What are the recent approaches to improving retrieval accuracy in
> Graph RAG systems?

The project should demonstrate a practical LangGraph workflow rather
than a basic chatbot or a sequence of independent LLM calls.

## 2. Goals

The finished project should demonstrate:

-   LangGraph `StateGraph` and shared state across nodes.
-   Tool calling and integration with an external research source.
-   Document extraction and vector-based retrieval.
-   Conditional edges based on evidence quality.
-   A cyclic workflow that can return to research when evidence is
    insufficient.
-   Structured outputs and citations in the final report.
-   A simple, usable interface and clear setup instructions.

## 3. Proposed workflow

1.  **Planner:** Break the user's question into focused research
    queries.
2.  **Researcher:** Search for relevant papers using the arXiv API.
3.  **Retriever:** Extract paper content and retrieve relevant passages.
4.  **Analyst:** Compare approaches, methodologies, strengths, and
    limitations.
5.  **Evidence checker:** Assess whether the report's claims are
    supported by retrieved passages.
6.  **Report generator:** Produce a structured report with source
    citations.

If the evidence checker finds gaps, the graph should route back to the
research step for another search. If the evidence is sufficient, the
graph proceeds to report generation.

## 4. LangGraph design

``` mermaid
flowchart TD
    A[User query] --> B[Planner]
    B --> C[Researcher: arXiv search]
    C --> D[Retriever: extract and search papers]
    D --> E[Analyst: compare findings]
    E --> F{Evidence sufficient?}
    F -- No --> C
    F -- Yes --> G[Report generator]
    G --> H[Cited research report]
```

### Core graph concepts

-   **StateGraph:** Store and pass shared workflow state between nodes.
-   **Conditional edges:** Decide whether to continue or repeat
    research.
-   **Tool calling:** Let the research node query an external source.
-   **Cycles:** Retry research when the available evidence is
    insufficient.
-   **Structured outputs:** Use defined schemas for intermediate results
    and the final report.

## 5. Suggested technology stack

  -----------------------------------------------------------------------
  Component                           Technology
  ----------------------------------- -----------------------------------
  Agent orchestration                 LangGraph

  Language model                      OpenAI model, such as GPT-4.1 mini,
                                      or another available model

  Research source                     arXiv API

  PDF extraction                      PyMuPDF

  Embeddings                          Sentence Transformers

  Vector store                        FAISS

  Backend and workflow                Python

  User interface                      Streamlit
  -----------------------------------------------------------------------

Keep the first version lightweight. Avoid adding infrastructure that is
not needed for a working demonstration.

## 6. One-day implementation plan

  -----------------------------------------------------------------------
  Time allocation         Task                    Expected outcome
  ----------------------- ----------------------- -----------------------
  Hour 1                  Project setup, state    Runnable LangGraph
                          schema, and graph       structure
                          skeleton                

  Hours 2--3              Planner and research    Query decomposition and
                          nodes                   arXiv search

  Hours 4--5              PDF extraction and      Relevant passages from
                          FAISS retrieval         papers

  Hour 6                  Analysis and            Comparisons and
                          evidence-checking nodes evidence assessment

  Hour 7                  Conditional routing and Working research loop
                          retry logic             

  Hour 8                  Streamlit interface,    End-to-end demo ready
                          testing, and README     to share
  -----------------------------------------------------------------------

**Scope rule:** A working end-to-end workflow with three or four
properly implemented nodes is better than six incomplete agents. If time
is short, simplify the number of nodes while preserving the conditional
research loop.

## 7. Suggested repository structure

``` text
agentic-research-assistant/
├── agents/
│   ├── planner.py
│   ├── researcher.py
│   ├── analyst.py
│   └── fact_checker.py
├── tools/
│   ├── arxiv_search.py
│   ├── pdf_extractor.py
│   └── vector_retriever.py
├── graph/
│   ├── state.py
│   └── workflow.py
├── app.py
├── requirements.txt
├── .env.example
└── README.md
```

The structure is a starting point; adjust it to keep the implementation
straightforward.

## 8. Definition of done

The project is ready to share when:

-   [ ] A user can submit a technical research question.
-   [ ] The planner creates focused search queries.
-   [ ] The research tool retrieves relevant papers.
-   [ ] The system extracts and retrieves useful paper passages.
-   [ ] The analysis compares findings using retrieved evidence.
-   [ ] The evidence checker can trigger a research retry.
-   [ ] The workflow can complete and produce a cited report.
-   [ ] The app runs locally using documented setup steps.
-   [ ] The repository includes a useful README and an architecture
    diagram.
-   [ ] At least one example query has been tested end to end.

## 9. GitHub presentation

The repository should include:

-   A concise project description and feature list.
-   The LangGraph architecture diagram.
-   Installation and run instructions.
-   An `.env.example` file listing required environment variables
    without real secrets.
-   A screenshot or short GIF of the working application.
-   One example query and its generated report.
-   A short explanation of the graph state, conditional routing, and
    retry behavior.

## 10. Important implementation guidance

-   Do not present unsupported model-generated claims as verified facts.
-   Preserve paper titles, URLs, and passage-level source references so
    the report can cite its evidence.
-   Set a maximum number of research retries to prevent an endless graph
    cycle.
-   Handle empty search results, failed downloads, malformed PDFs, and
    model errors.
-   Keep API keys in environment variables; never commit `.env` or
    credentials.
-   Make it clear when evidence is weak or unavailable rather than
    fabricating citations.

## 11. Final deliverable

A public GitHub repository containing a working **Agentic Research &
Analysis Assistant**, with a short demo and clear documentation.

The strongest part of the demonstration should be the LangGraph control
flow: the system researches, evaluates its evidence, and conditionally
loops back for more information before producing its final answer.
