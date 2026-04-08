# Simple Architecture Flowchart

```mermaid
flowchart TD
  U[User] -->|Preferences: location, budget, cuisine,\nmin rating, extra prefs| API[Application Layer\nAPI/UI]

  subgraph REC[Recommendation Service]
    P[Preference Normalizer\n- normalize location/cuisine\n- map budget->cost bucket\n- validate min rating]
    SEL[Deterministic Candidate Selector\n- hard filters\n- lightweight scoring\n- pick top K]
    PB[Prompt Builder\n- inject preferences\n- add candidates (top K)\n- enforce JSON output rules]
    LLM[Gemini Client\nRank + explanations]
    VAL[Output Parser + Validator\n- JSON parse\n- schema validation\n- candidate-id grounding\n- retry/repair or fallback]
    JOIN[Join Details + Format Response\n- attach name/cuisine/rating/cost\n- keep LLM explanation]
  end

  subgraph DATA[Data Foundation]
    HF[(Hugging Face Zomato Dataset)]
    ING[Ingestion + Preprocessing\n- extract fields\n- normalize schema\n- derive cost buckets]
    CAT[(Restaurant Catalog\nProcessed artifact + indexes)]
    HF --> ING --> CAT
  end

  API --> P --> SEL
  CAT --> SEL
  SEL --> PB --> LLM --> VAL --> JOIN --> API

  API --> OUT[Recommendations Output\nTop N with explanations]
```

## Notes
- **Hard constraints** (location/cuisine/min rating/budget) are enforced **before** the LLM.
- The LLM is used for **ranking + natural-language explanations**, constrained by a **strict JSON contract**.
- Validation ensures the LLM only references restaurants from the provided candidate list.
- Gemini API key is loaded from `.env` via `GEMINI_API_KEY`.

