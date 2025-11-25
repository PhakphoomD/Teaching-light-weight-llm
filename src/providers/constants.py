"""
Gemini API Rate Limits and Model Constants

This module stores API rate limits for each Gemini model tier based on the 
free tier quotas from Google AI Studio. These limits are used for intelligent
rate limiting and cost estimation.

Rate limit definitions:
- RPM: Requests Per Minute
- TPM: Tokens Per Minute  
- RPD: Requests Per Day

Reference: https://ai.google.dev/pricing
"""

from typing import Dict, TypedDict, Any


class ModelLimits(TypedDict):
    """Type definition for model rate limits."""
    RPM: int  # Requests Per Minute
    TPM: int  # Tokens Per Minute
    RPD: int  # Requests Per Day


# Gemini API rate limits (free tier)
# Reference: https://ai.google.dev/pricing (as of Nov 2025)
# This is the SINGLE SOURCE OF TRUTH for all rate limits
MODEL_LIMITS: Dict[str, ModelLimits] = {
    "gemini-2.5-flash": {
        "RPM": 10,  
        "TPM": 250000,
        "RPD": 250,
    },
    "gemini-2.5-flash-lite": {
        "RPM": 15,
        "TPM": 250000,
        "RPD": 1000,  
    },
    "gemini-2.0-flash-lite": {
        "RPM": 15,
        "TPM": 250000,
        "RPD": 1000, 
    },
    "gemini-2.5-pro": {
        "RPM": 2,
        "TPM": 125000,
        "RPD": 50,
    },
}

# Default fallback limits for unknown models
DEFAULT_LIMITS: ModelLimits = {
    "RPM": 2,
    "TPM": 50000,
    "RPD": 50,
}


def get_model_limits(model_name: str) -> ModelLimits:
    """
    Retrieve rate limits for a specific Gemini model.
    
    Args:
        model_name: Full model identifier (e.g., "gemini-2.0-flash-lite")
    
    Returns:
        ModelLimits dictionary containing RPM, TPM, and RPD values
        
    Examples:
        >>> limits = get_model_limits("gemini-2.0-flash-lite")
        >>> print(limits["RPM"])
        30
        >>> print(limits["TPM"])
        1000000
        >>> print(limits["RPD"])
        200
    """
    return MODEL_LIMITS.get(model_name, DEFAULT_LIMITS)


def list_available_models() -> list[str]:
    """
    Get list of all Gemini models with defined rate limits.
    
    Returns:
        List of model names
    """
    return list(MODEL_LIMITS.keys())


def get_fastest_model() -> str:
    """
    Get the model with highest RPM (fastest for sequential requests).
    
    Returns:
        Model name with highest requests per minute
    """
    return max(MODEL_LIMITS.items(), key=lambda x: x[1]["RPM"])[0]


def get_highest_throughput_model() -> str:
    """
    Get the model with highest TPM (best for large batches).
    
    Returns:
        Model name with highest tokens per minute
    """
    return max(MODEL_LIMITS.items(), key=lambda x: x[1]["TPM"])[0]


def estimate_experiment_time(
    model_name: str,
    num_questions: int,
    avg_rounds_per_question: float = 2.0,
    llm_reviewer_enabled: bool = False,
    use_borderline: bool = True,
    borderline_ratio: float = 0.6
) -> Dict[str, Any]:
    """
    Estimate experiment runtime and check rate limits.
    
    Args:
        model_name: Model to use (e.g., "gemini-2.5-flash")
        num_questions: Number of questions in dataset
        avg_rounds_per_question: Average refinement rounds per question
        llm_reviewer_enabled: Whether LLM reviewer is enabled
        use_borderline: Whether using borderline mode (only review uncertain scores)
        borderline_ratio: Fraction of answers in borderline range (default 0.6)
    
    Returns:
        Dictionary with:
            - total_calls: Total API calls
            - calls_per_minute: Calls distributed per minute
            - estimated_minutes: Estimated runtime in minutes
            - rpm_limit: Model's RPM limit
            - rpd_limit: Model's RPD limit
            - within_rpm: Whether within RPM limit
            - within_rpd: Whether within RPD limit
            - warning: Warning message if limits exceeded
    
    Example:
        >>> info = estimate_experiment_time(
        ...     "gemini-2.5-flash",
        ...     num_questions=10,
        ...     llm_reviewer_enabled=True,
        ...     use_borderline=True
        ... )
        >>> print(f"Estimated time: {info['estimated_minutes']:.1f} minutes")
        >>> if not info['within_rpm']:
        ...     print(f"WARNING: {info['warning']}")
    """
    limits = get_model_limits(model_name)
    rpm_limit = limits["RPM"]
    rpd_limit = limits["RPD"]
    
    # Calculate total rounds
    total_rounds = num_questions * avg_rounds_per_question
    
    # Calculate API calls based on LLM reviewer settings
    teacher_calls = 0.0
    reviewer_calls = 0.0
    
    if llm_reviewer_enabled:
        if use_borderline:
            # Borderline mode: LLM reviewer only for uncertain scores
            teacher_calls = total_rounds  # Teacher always generates hints
            reviewer_calls = total_rounds * borderline_ratio  # Only borderline cases
            total_calls = teacher_calls + reviewer_calls
        else:
            # Full mode: LLM reviewer for all answers
            teacher_calls = total_rounds
            reviewer_calls = total_rounds
            total_calls = teacher_calls + reviewer_calls
    else:
        # No LLM reviewer: only teacher calls
        teacher_calls = total_rounds
        total_calls = total_rounds
    
    # Calculate runtime
    if total_calls <= rpm_limit:
        # Can complete within 1 minute
        estimated_minutes = 1.0
    else:
        # Need multiple minutes
        estimated_minutes = total_calls / rpm_limit
    
    # Check limits
    within_rpm = (total_calls / estimated_minutes) <= rpm_limit
    within_rpd = total_calls <= rpd_limit
    
    # Generate warning
    warning = None
    if not within_rpd:
        warning = f"CRITICAL: {total_calls} calls exceeds daily limit ({rpd_limit} RPD)"
    elif not within_rpm:
        warning = f"WARNING: May experience rate limiting (calls distributed over {estimated_minutes:.1f} min)"
    
    return {
        "total_calls": int(total_calls),
        "teacher_calls": int(teacher_calls) if llm_reviewer_enabled else int(total_calls),
        "reviewer_calls": int(reviewer_calls) if llm_reviewer_enabled else 0,
        "calls_per_minute": total_calls / estimated_minutes,
        "estimated_minutes": estimated_minutes,
        "rpm_limit": rpm_limit,
        "rpd_limit": rpd_limit,
        "within_rpm": within_rpm,
        "within_rpd": within_rpd,
        "warning": warning,
    }
