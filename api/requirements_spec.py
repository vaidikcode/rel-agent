"""Requirement definitions: id, label, prompt for the LLM."""
REQUIREMENTS = [
    {
        "id": "phd_ml",
        "label": "PhD or PhD-level experience with machine learning",
        "prompt": "Does the candidate have a PhD or PhD-level experience with machine learning? Consider equivalent research experience (e.g. first-author top-tier ML papers, years in research).",
    },
    {
        "id": "generative_sota",
        "label": "Research on SOTA generative models (past 3 years)",
        "prompt": "In the past three years, has the candidate done research or impactful innovative work on state-of-the-art generative models, such as LLMs, flow-matching, or diffusion-based models (beyond just applying existing models)?",
    },
    {
        "id": "built_from_scratch",
        "label": "Hands-on experience building generative models from scratch",
        "prompt": "Has the candidate been the main driver in building generative models from scratch (hands-on implementation, not only using existing libraries)?",
    },
    {
        "id": "multimodal_visual",
        "label": "Research on multimodal models including visual (past 3 years)",
        "prompt": "In the past three years, has the candidate done research on multimodal models that include visual modalities?",
    },
    {
        "id": "audio_experience",
        "label": "Experience working with audio",
        "prompt": "Does the candidate have experience working with audio (e.g. speech, music, audio ML)?",
    },
    {
        "id": "job_stability",
        "label": "Reasonable job tenure (~1 year per job minimum)",
        "prompt": "Has the candidate not switched jobs too often? Prefer roughly at least 1 year per role; flag if many very short stints.",
    },
]

REQUIREMENT_IDS = [r["id"] for r in REQUIREMENTS]
WEIGHT_PER_REQUIREMENT = 1
