import argparse
import json
from pathlib import Path
from pydoc import doc
from urllib.parse import quote

from prov.dot import prov_to_dot
from prov.model import PROV, PROV_TYPE, ProvDocument


def _scalar_attributes(prefix, values):
    return {
        f"lcr:{prefix}_{key}": value
        for key, value in values.items()
        if value is not None
    }


def _without_none(attributes):
    return {key: value for key, value in attributes.items() if value is not None}


def convert_provenance_record(record):
    run_id = record["run_id"]
    repositories = record.get("repositories", [])
    extractions = record.get("github_diff_extractions", [])
    gemini_calls = record.get("gemini_calls", [])
    summary = record.get("summary") or {}
    gemini_config = record.get("gemini_config") or {}

    document = ProvDocument()
    document.add_namespace("lcr", "urn:llm-code-reviewer:prov:")
    document.set_default_namespace(
        f"urn:llm-code-reviewer:{quote(run_id, safe='')}:"
    )

    app_agent = document.agent(
        "agent_application",
        {
            PROV_TYPE: PROV["SoftwareAgent"],
            "prov:label": "LLM Code Reviewer",
            "lcr:role": "application",
        },
    )
    github_agent = document.agent(
        "agent_github",
        {
            PROV_TYPE: PROV["SoftwareAgent"],
            "prov:label": "GitHub",
            "lcr:role": "source-control",
        },
    )
    model = gemini_config.get("model", "Gemini")
    gemini_agent = document.agent(
        "agent_gemini",
        {
            PROV_TYPE: PROV["SoftwareAgent"],
            "prov:label": f"Google Gemini ({model})",
            "lcr:role": "language-model",
            "lcr:model": model,
        },
    )

    run_attributes = {
        "lcr:status": record.get("status", "unknown"),
        "lcr:durationSeconds": record.get("duration_sec", 0),
        **_scalar_attributes("geminiConfig", gemini_config),
        **_scalar_attributes("summary", summary),
    }
    for key in ("error_type", "error_message"):
        if record.get(key) is not None:
            run_attributes[f"lcr:{key}"] = record[key]

    run_activity = document.activity(
        "activity_run",
        record.get("started_at"),
        record.get("ended_at"),
        _without_none(run_attributes),
    )
    document.wasAssociatedWith(run_activity, app_agent)
    run_entity = document.entity(
        "entity_run_record",
        {
            "prov:label": f"Operational provenance record {run_id}",
            "lcr:status": record.get("status", "unknown"),
        },
    )
    document.wasGeneratedBy(run_entity, run_activity)

    repository_entities = {}
    artifact_entities = {}

    def repository_entity(owner, name, url=None):
        key = (owner, name)
        if key not in repository_entities:
            attributes = {
                "prov:label": f"{owner}/{name}",
                "lcr:owner": owner,
                "lcr:repositoryName": name,
            }
            if url is not None:
                attributes["lcr:url"] = url
            repository_entities[key] = document.entity(
                f"entity_repository_{len(repository_entities)}", attributes
            )
        return repository_entities[key]

    def artifact_entity(owner, name, artifact_type, artifact_id):
        key = (owner, name, artifact_type, str(artifact_id))
        if key not in artifact_entities:
            artifact = document.entity(
                f"entity_artifact_{len(artifact_entities)}",
                {
                    "prov:label": f"{owner}/{name} {artifact_type} {artifact_id}",
                    "lcr:artifactType": artifact_type,
                    "lcr:artifactId": str(artifact_id),
                },
            )
            document.wasDerivedFrom(artifact, repository_entity(owner, name))
            artifact_entities[key] = artifact
        return artifact_entities[key]

    for repo in repositories:
        owner = repo["owner"]
        name = repo["repo"]
        repository = repository_entity(owner, name, repo.get("url"))
        document.used(run_activity, repository)

        for pull_request in repo.get("pull_requests", []):
            artifact_entity(owner, name, "pull_request", pull_request)

        for commit in repo.get("commits", []):
            commit_hash = (
                commit["commit_hash"] if isinstance(commit, dict) else commit
            )
            artifact_entity(owner, name, "commit", commit_hash)

    extraction_links = {}
    for index, extraction in enumerate(extractions):
        owner = extraction["owner"]
        name = extraction["repo"]
        artifact_type = extraction["artifact_type"]
        artifact_id = extraction["artifact_id"]
        artifact = artifact_entity(owner, name, artifact_type, artifact_id)

        activity = document.activity(
            f"activity_diff_extraction_{index}",
            extraction.get("started_at"),
            extraction.get("completed_at"),
            _without_none(
                {
                    "lcr:status": (
                        "succeeded" if extraction.get("success") else "failed"
                    ),
                    "lcr:durationSeconds": extraction.get("duration_sec", 0),
                    "lcr:diffSizeCharacters": extraction.get(
                        "diff_size_characters", 0
                    ),
                    "lcr:errorType": extraction.get("error_type"),
                    "lcr:errorMessage": extraction.get("error_message"),
                }
            ),
        )
        document.used(activity, repository_entity(owner, name))
        document.used(activity, artifact)
        document.wasAssociatedWith(activity, app_agent)
        document.wasAssociatedWith(activity, github_agent)

        diff = None
        if extraction.get("success"):
            diff = document.entity(
                f"entity_diff_{index}",
                {
                    "prov:label": (
                        f"Diff for {owner}/{name} {artifact_type} {artifact_id}"
                    ),
                    "lcr:characterCount": extraction.get(
                        "diff_size_characters", 0
                    ),
                },
            )
            document.wasGeneratedBy(diff, activity)
            document.wasDerivedFrom(diff, artifact)
        extraction_links[
            (owner, name, artifact_type, str(artifact_id))
        ] = (activity, diff)

    for index, call in enumerate(gemini_calls):
        owner = call["owner"]
        name = call["repo"]
        artifact_type = call["artifact_type"]
        artifact_id = call["artifact_id"]
        key = (owner, name, artifact_type, str(artifact_id))
        extraction_activity, diff = extraction_links.get(key, (None, None))

        activity = document.activity(
            f"activity_gemini_call_{index}",
            call.get("started_at"),
            None,
            _without_none(
                {
                    "lcr:status": call.get("status", "unknown"),
                    "lcr:operation": call.get("operation", "unspecified"),
                    "lcr:attempt": call.get("attempt", 1),
                    "lcr:isTimeout": bool(call.get("is_timeout", False)),
                    "lcr:durationSeconds": call.get("duration_sec", 0),
                    "lcr:inputTokens": call.get("input_tokens", 0),
                    "lcr:outputTokens": call.get("output_tokens", 0),
                    "lcr:errorType": call.get("error_type"),
                    "lcr:errorMessage": call.get("error_message"),
                }
            ),
        )
        input_entity = (
            diff
            if diff is not None
            else artifact_entity(owner, name, artifact_type, artifact_id)
        )
        document.used(activity, input_entity)
        if extraction_activity is not None and diff is not None:
            document.wasInformedBy(activity, extraction_activity)
        document.wasAssociatedWith(activity, app_agent)
        document.wasAssociatedWith(activity, gemini_agent)

        if call.get("status") == "succeeded":
            response = document.entity(
                f"entity_gemini_response_{index}",
                {
                    "prov:label": (
                        f"Gemini response metadata for {artifact_type} {artifact_id}"
                    ),
                    "lcr:outputTokens": call.get("output_tokens", 0),
                },
            )
            document.wasGeneratedBy(response, activity)
            if diff is not None:
                document.wasDerivedFrom(response, diff)

    return document


def convert_provenance_file(input_path):
    source = Path(input_path)
    record = json.loads(source.read_text(encoding="utf-8"))
    document = convert_provenance_record(record)
    destination = (
    source.with_name(f"{source.stem}.prov.jsonld")
    )
    destination.write_text(
        document.serialize(format="jsonld", context="embed", indent=2) + "\n",
        encoding="utf-8",
    )
    prov_to_dot(document, direction="RL").write_svg(str(destination.with_suffix(".svg")))
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="provenance_run_<id>.json")
    args = parser.parse_args(argv)
    output = convert_provenance_file(args.input)
    print(f"PROV-JSON-LD graph saved to {output}")
    print(f"SVG graph saved to {output.with_suffix('.svg')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
