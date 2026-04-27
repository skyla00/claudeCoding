"""분석 provider 선택 인터페이스."""

from __future__ import annotations

from collections.abc import Iterator

from analysis.config import get_analysis_provider


def analyze(prompt: str) -> str:
    provider = get_analysis_provider()
    if provider == "claude":
        from analysis.claude import analyze as analyze_with_claude

        return analyze_with_claude(prompt)
    if provider == "gemini":
        from analysis.gemini import analyze as analyze_with_gemini

        return analyze_with_gemini(prompt)
    raise ValueError(f"지원하지 않는 분석 provider: {provider}")


def analyze_stream(prompt: str) -> Iterator[str]:
    provider = get_analysis_provider()
    if provider == "claude":
        from analysis.claude import analyze_stream as stream_with_claude

        yield from stream_with_claude(prompt)
        return
    if provider == "gemini":
        from analysis.gemini import analyze_stream as stream_with_gemini

        yield from stream_with_gemini(prompt)
        return
    raise ValueError(f"지원하지 않는 분석 provider: {provider}")
