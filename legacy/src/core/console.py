"""
Console Output Module with Rich Integration

Provides professional console output formatting for experiments using Rich library.
Includes structured logging, progress tracking, and formatted experiment blocks.
"""

import sys
import logging
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path

# Type checking imports
if TYPE_CHECKING:
    from rich.console import Console as RichConsole
    from rich.progress import Progress as RichProgress

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.progress import (
        Progress,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
        SpinnerColumn,
        MofNCompleteColumn
    )
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    # Dummy classes for type checking when Rich is not installed
    Console = None  # type: ignore
    RichHandler = None  # type: ignore
    Panel = None  # type: ignore
    Progress = None  # type: ignore
    BarColumn = None  # type: ignore
    TextColumn = None  # type: ignore
    TimeRemainingColumn = None  # type: ignore
    SpinnerColumn = None  # type: ignore
    MofNCompleteColumn = None  # type: ignore
    Table = None  # type: ignore
    box = None  # type: ignore
    print("  Warning: 'rich' not installed. Install with: pip install rich")
    print("   Using plain text output instead.\n")

# Global console instance
console: Optional['RichConsole'] = Console() if RICH_AVAILABLE else None  # type: ignore


def setup_rich_logging(level: int = logging.INFO) -> None:
    """
    Setup logging with Rich handler for beautiful console output.
    
    Args:
        level: Logging level (default: INFO)
    
    Example:
        >>> setup_rich_logging(logging.DEBUG)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("This will be beautifully formatted!")
    """
    if not RICH_AVAILABLE or not console or not RichHandler:
        # Fallback to basic logging
        logging.basicConfig(
            level=level,
            format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        return
    
    # Configure Rich logging handler
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
        tracebacks_show_locals=False
    )
    
    # Custom formatter
    formatter = logging.Formatter(
        fmt="%(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]"
    )
    rich_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add Rich handler
    root_logger.addHandler(rich_handler)


def print_experiment_block(
    experiment_id: str,
    question_id: str,
    attempt: int,
    total_attempts: int,
    question: str,
    answer: str,
    metrics: Optional[Dict[str, float]] = None,
    hint: Optional[str] = None,
    progress_current: int = 0,
    progress_total: int = 0,
    log_file: Optional[str] = None
) -> None:
    """
    Print a formatted experiment block showing results for one question/attempt.
    
    Args:
        experiment_id: Unique experiment identifier
        question_id: Question identifier
        attempt: Current attempt number (1-indexed)
        total_attempts: Total number of attempts for this question
        question: The question text
        answer: The student's answer
        metrics: Dictionary of evaluation metrics (EM, F1, BLEU, etc.)
        hint: Hint provided to the student (if any)
        progress_current: Current question number in the experiment
        progress_total: Total number of questions in the experiment
        log_file: Path to the log file
    
    Example:
        >>> print_experiment_block(
        ...     experiment_id="baseline_test",
        ...     question_id="alpaca-2",
        ...     attempt=2,
        ...     total_attempts=3,
        ...     question="What is the capital of France?",
        ...     answer="Paris is the capital of France.",
        ...     metrics={"EM": 0.5, "F1": 0.75, "BLEU": 0.4, "ROUGE-L": 0.8, "BERT-F1": 0.85},
        ...     hint="Consider the city name only",
        ...     progress_current=5,
        ...     progress_total=20,
        ...     log_file="logs/runs/baseline_test.jsonl"
        ... )
    """
    if not RICH_AVAILABLE:
        _print_experiment_block_plain(
            experiment_id, question_id, attempt, total_attempts,
            question, answer, metrics, hint, progress_current, progress_total, log_file
        )
        return
    
    # Create formatted block
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Truncate long texts
    question_display = question[:200] + "..." if len(question) > 200 else question
    answer_display = answer[:300] + "..." if len(answer) > 300 else answer
    
    # Build content
    content_lines = []
    
    # Header
    header = f"[bold cyan]{timestamp}[/bold cyan] | [bold]INFO[/bold] | Experiment [yellow]{experiment_id}[/yellow] | Q [cyan]{question_id}[/cyan] (attempt {attempt}/{total_attempts})"
    content_lines.append(header)
    content_lines.append("")
    
    # Question
    content_lines.append(f"[bold]Question:[/bold]   {question_display}")
    content_lines.append("")
    
    # Answer
    content_lines.append(f"[bold]Final Answer:[/bold]")
    content_lines.append(answer_display)
    content_lines.append("")
    
    # Metrics
    if metrics:
        metrics_str = " | ".join([
            f"[cyan]{k}:[/cyan] [green]{v:.2f}[/green]" if v >= 0.5 else f"[cyan]{k}:[/cyan] [red]{v:.2f}[/red]"
            for k, v in metrics.items()
        ])
        content_lines.append(metrics_str)
        content_lines.append("")
    
    # Hint
    if hint:
        hint_display = hint[:150] + "..." if len(hint) > 150 else hint
        content_lines.append(f"[bold]Hint Used:[/bold]  [dim]{hint_display}[/dim]")
        content_lines.append("")
    
    # Progress bar
    if progress_total > 0:
        progress_pct = (progress_current / progress_total) * 100
        bar_width = 30
        filled = int((progress_pct / 100) * bar_width)
        bar = " " * filled + " " * (bar_width - filled)
        content_lines.append(f"[bold]Progress:[/bold]   {bar} [cyan]{progress_pct:.0f}%[/cyan] ({progress_current}/{progress_total})")
        content_lines.append("")
    
    # Log file
    if log_file:
        content_lines.append(f"[bold]Log file:[/bold]   [dim]{log_file}[/dim]")
    
    # Print block
    if console:
        console.print("")
        console.print("=" * 120)
        for line in content_lines:
            console.print(line)
        console.print("=" * 120)
        console.print("")


def _print_experiment_block_plain(
    experiment_id: str,
    question_id: str,
    attempt: int,
    total_attempts: int,
    question: str,
    answer: str,
    metrics: Optional[Dict[str, float]] = None,
    hint: Optional[str] = None,
    progress_current: int = 0,
    progress_total: int = 0,
    log_file: Optional[str] = None
) -> None:
    """Plain text version of print_experiment_block for when Rich is not available."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print("\n" + "=" * 120)
    print(f"{timestamp} | INFO | Experiment {experiment_id} | Q {question_id} (attempt {attempt}/{total_attempts})")
    print("")
    
    question_display = question[:200] + "..." if len(question) > 200 else question
    print(f"Question   : {question_display}")
    print("")
    
    answer_display = answer[:300] + "..." if len(answer) > 300 else answer
    print("Final Answer:")
    print(answer_display)
    print("")
    
    if metrics:
        metrics_str = " | ".join([f"{k}: {v:.2f}" for k, v in metrics.items()])
        print(metrics_str)
        print("")
    
    if hint:
        hint_display = hint[:150] + "..." if len(hint) > 150 else hint
        print(f"Hint Used  : {hint_display}")
        print("")
    
    if progress_total > 0:
        progress_pct = (progress_current / progress_total) * 100
        bar_width = 30
        filled = int((progress_pct / 100) * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"Progress   : {bar} {progress_pct:.0f}% ({progress_current}/{progress_total})")
        print("")
    
    if log_file:
        print(f"Log file   : {log_file}")
    
    print("=" * 120 + "\n")


def create_progress_bar(description: str = "Processing") -> Optional[Any]:  # type: ignore
    """
    Create a Rich progress bar for tracking long-running operations.
    
    Args:
        description: Description text for the progress bar
    
    Returns:
        Progress object if Rich is available, None otherwise
    
    Example:
        >>> progress = create_progress_bar("Training student")
        >>> if progress:
        ...     with progress:
        ...         task = progress.add_task("[cyan]Training...", total=100)
        ...         for i in range(100):
        ...             progress.update(task, advance=1)
        ...             time.sleep(0.1)
    """
    if not RICH_AVAILABLE or not all([Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn]):
        return None
    
    return Progress(  # type: ignore
        SpinnerColumn(),  # type: ignore
        TextColumn("[bold blue]{task.description}"),  # type: ignore
        BarColumn(bar_width=40),  # type: ignore
        MofNCompleteColumn(),  # type: ignore
        TextColumn(" "),  # type: ignore
        TimeRemainingColumn(),  # type: ignore
        console=console,
        transient=False  # Keep progress visible after completion
    )


def print_summary_table(
    data: list[Dict[str, Any]],
    title: str = "Summary",
    columns: Optional[list[str]] = None
) -> None:
    """
    Print a formatted summary table.
    
    Args:
        data: List of dictionaries with data to display
        title: Table title
        columns: List of column names to display (uses all keys if None)
    
    Example:
        >>> data = [
        ...     {"Model": "gemini-2.0-flash-lite", "EM": 0.45, "F1": 0.67, "Latency": 120},
        ...     {"Model": "gemini-2.5-flash-lite", "EM": 0.52, "F1": 0.71, "Latency": 150},
        ... ]
        >>> print_summary_table(data, title="Teacher Model Comparison")
    """
    if not RICH_AVAILABLE or not data:
        # Plain text fallback
        print(f"\n=== {title} ===")
        if not data:
            print("No data to display")
            return
        
        for i, row in enumerate(data, 1):
            print(f"\n{i}. {row}")
        print("")
        return
    
    # Determine columns
    if columns is None:
        columns = list(data[0].keys())
    
    # Create table
    if not Table or not box:
        # Fallback if Rich classes not available
        for i, row in enumerate(data, 1):
            print(f"\n{i}. {row}")
        print("")
        return
    
    table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")  # type: ignore
    
    # Add columns
    for col in columns:
        table.add_column(col, justify="left" if isinstance(data[0].get(col), str) else "right")
    
    # Add rows
    for row in data:
        table.add_row(*[str(row.get(col, "N/A")) for col in columns])
    
    # Print table
    if console:
        console.print("")
        console.print(table)
        console.print("")


def print_header(text: str, style: str = "bold cyan") -> None:
    """
    Print a formatted header.
    
    Args:
        text: Header text
        style: Rich style string
    
    Example:
        >>> print_header("Starting Baseline Experiment")
    """
    if not RICH_AVAILABLE or not console or not Panel:
        print(f"\n{'=' * 80}")
        print(f"  {text}")
        print(f"{'=' * 80}\n")
        return
    
    console.print("")
    console.print(Panel.fit(  # type: ignore
        f"[{style}]{text}[/{style}]",
        border_style=style.split()[1] if " " in style else style
    ))
    console.print("")


def print_success(message: str) -> None:
    """Print a success message."""
    if RICH_AVAILABLE and console:
        console.print(f"[green] [/green] {message}")
    else:
        print(f"  {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    if RICH_AVAILABLE and console:
        console.print(f"[red] [/red] {message}")
    else:
        print(f"  {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    if RICH_AVAILABLE and console:
        console.print(f"[yellow] [/yellow] {message}")
    else:
        print(f"  {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    if RICH_AVAILABLE and console:
        console.print(f"[blue] [/blue] {message}")
    else:
        print(f"  {message}")


# Export commonly used items
__all__ = [
    'console',
    'setup_rich_logging',
    'print_experiment_block',
    'create_progress_bar',
    'print_summary_table',
    'print_header',
    'print_success',
    'print_error',
    'print_warning',
    'print_info',
    'RICH_AVAILABLE'
]
