import time
from datetime import datetime, timezone


class ProvenanceRecorder:

    def __init__(self, repos_file_path):
        self.started_at = datetime.now(timezone.utc)
        self._start_counter = time.perf_counter()
        self.run_id = self.started_at.astimezone().strftime("%Y%m%d_%H%M%S")
        self.github_diff_extractions = []
        self.repository_specs = []

    def set_repository_specs(self, repositories):
        self.repository_specs = [
            {
                "owner": repo.get("owner"),
                "repo": repo.get("repo"),
                "url": repo.get("url"),
                "osv_report": str(repo.get("osv_report", "")).lower() == "true",
                "pull_requests": list(repo.get("pull_requests", [])),
                "commits": list(repo.get("commits", [])),
            }
            for repo in repositories
        ]

    def record_diff_extraction(
        self, owner, repo, artifact_type, artifact_id, duration_sec, diff_content,
        started_at=None, error_type=None, error_message=None
    ):
        self.github_diff_extractions.append({
            "owner": owner,
            "repo": repo,
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_sec": duration_sec,
            "success": diff_content is not None,
            "error_type": error_type,
            "error_message": error_message,
            "diff_size_characters": len(diff_content) if diff_content is not None else 0,
        })

    def extract_diff(self, owner, repo, artifact_type, artifact_id, extractor):
        started_at = datetime.now(timezone.utc)
        start = time.perf_counter()
        try:
            diff_content = extractor()
        except Exception as error:
            print(f"Erro ao extrair diff para {owner}/{repo} {artifact_type} {artifact_id}: {error}")
            self.record_diff_extraction(
                owner, repo, artifact_type, artifact_id,
                time.perf_counter() - start, None, started_at,
                type(error).__name__, str(error)
            )
            raise

        self.record_diff_extraction(
            owner, repo, artifact_type, artifact_id,
            time.perf_counter() - start, diff_content, started_at
        )
        return diff_content

    def build_record(self, gemini_calls, status, error=None, gemini_config=None):
        ended_at = datetime.now(timezone.utc)
        retries = sum(max(call["attempt"] - 1, 0) for call in gemini_calls)
        timeouts = sum(call["is_timeout"] for call in gemini_calls)
        input_tokens = sum(call.get("input_tokens", 0) for call in gemini_calls)
        output_tokens = sum(call.get("output_tokens", 0) for call in gemini_calls)
        error_type = type(error).__name__ if isinstance(error, BaseException) else error
        error_message = str(error) if isinstance(error, BaseException) else None

        return {
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_sec": time.perf_counter() - self._start_counter,
            "repositories": self.repository_specs,
            "error_type": error_type,
            "error_message": error_message,
            "gemini_config": gemini_config,
            "summary": {
                "github_diff_extractions": len(self.github_diff_extractions),
                "github_diff_extraction_failures": sum(
                    not item["success"] for item in self.github_diff_extractions
                ),
                "github_diff_extraction_time_sec": sum(
                    item["duration_sec"] for item in self.github_diff_extractions
                ),
                "gemini_api_calls": len(gemini_calls),
                "gemini_response_time_sec": sum(
                    call["duration_sec"] for call in gemini_calls
                ),
                "gemini_retries": retries,
                "gemini_timeouts": timeouts,
                "gemini_input_tokens": input_tokens,
                "gemini_output_tokens": output_tokens,
            },
            "github_diff_extractions": self.github_diff_extractions,
            "gemini_calls": gemini_calls,
        }

