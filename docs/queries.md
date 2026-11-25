# The five study queries

A student asks **Arrow**, an AI chat-assistant app (sidebar with chats, a conversation thread and a message box), five
questions. Each is a **different kind of question** on a light, everyday topic, so the data shows how people react to
different presentations, not just to one kind of answer.

| # | Topic | Query | Kind of question | What the answer naturally contains |
|---|---|---|---|---|
| Q1 | Machine learning | *List the different machine learning models used for data analysis.* (the instructor's example) | **Comparison** | decision tree, table, cards |
| Q2 | Web & networks | *What happens when I type a website address into my browser?* | **Concept** (how something works) | flow diagram, steps, timing chart, analogy |
| Q3 | Computer systems | *Why does my computer slow down when I open too many apps?* | **Cause and effect** | memory chart, cause-effect flow, worked example |
| Q4 | Study skills | *How should I prepare for my final exams in 2 weeks?* | **Plan** | timeline, steps, schedule table |
| Q5 | Grades | *How do I calculate my GPA?* | **Calculation** | formula, worked example table, bar chart |

Q2 and Q3 are light computing questions everyone meets in daily life; Q4 and Q5 are real student worries, so they are
also likely to produce genuine emotional reactions.

## Six looks per answer

Every answer exists in the same six presentations, so we can see **which presentation helps under which emotion**:

| Look | Shown to students as | Typical content |
|---|---|---|
| `text` | Paragraphs | a written explanation |
| `visual` | Visual | charts and diagrams with short captions |
| `steps` | Step by step | numbered steps |
| `example` | Worked example | a concrete example with numbers |
| `summary` | Summary | a short table / cheat sheet |
| `simple` | Simple | plain words and an everyday comparison |

The facts are the same in all six looks. Each query also has one multiple-choice **quiz question**, asked after the answer, to
check understanding.

## Where the content lives

- `content/queries/q1.yaml` … `q5.yaml`: the query, the quiz and the six looks, written as **blocks** (heading, paragraph,
  bullets, steps, table, chart, diagram, callout, example, formula, cards). This block format is what the future LLM agent will
  generate live; the same renderer (`web/genui/render.js`) draws both.
- The content was **generated once by an LLM (Claude) and frozen**, so every participant sees identical answers. Each file
  records its provenance (`generated_by`, `generated_on`, `reviewed_by`, `status`).
- **Team review:** run `python run.py preview` to see every answer in every look. When a query has been checked, set
  `reviewed_by` and `status: reviewed` in its file. Do not edit content after data collection has started.
