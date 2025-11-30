#!/usr/bin/env python3
"""
analise_sonar.py (final)

Suporta:
 - checkout/clone seguro de PRs e commits
 - extração do diff (linhas envolvidas)
 - compilação automática para projetos Java com Maven (se houver pom.xml)
 - execução do sonar-scanner (multi-linguagem)
 - configuração automática de sonar.java.binaries quando aplicável
 - consulta de issues do Sonar arquivo-a-arquivo
 - relatório salvo no diretório do script

Requisitos:
 - sonar-scanner no PATH ou configure SONAR_SCANNER_PATH (env)
 - Maven disponível (opcional, recomendado para Java). Pode usar MAVEN_EXECUTABLE_PATH var no topo.
 - Defina SONAR_PROJECT_KEY e SONAR_TOKEN via variáveis de ambiente ou llm_code_reviewer.config
"""
import re
import os
import sys
import subprocess
from datetime import datetime
from urllib.parse import urlparse
import requests
import shutil

# try config module for GITHUB_TOKEN (optional)
try:
    from llm_code_reviewer import config
    GITHUB_TOKEN = getattr(config, "GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
except Exception:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Sonar / environment configuration
SONAR_TOKEN = os.environ.get("SONAR_TOKEN")
SONAR_URL = os.environ.get("SONAR_URL", "http://localhost:9000")
SONAR_PROJECT_KEY = os.environ.get("SONAR_PROJECT_KEY")
BASE_REPOS_PATH = os.environ.get("BASE_REPOS_PATH")

# Maven executable path (you already had this)
MAVEN_EXECUTABLE_PATH = os.environ.get("MAVEN_EXECUTABLE_PATH")

# Sonar scanner path (optional). If empty, script will call "sonar-scanner" and rely on PATH.
SONAR_SCANNER_PATH = os.environ.get("SONAR_SCANNER_PATH", "")

USE_SONAR_BRANCH_NAME = bool(os.environ.get("USE_SONAR_BRANCH_NAME", "False").lower() in ("1","true","yes"))

# Headers
GITHUB_API_HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {"Accept": "application/vnd.github.v3+json"}
SONAR_API_HEADERS = {"Authorization": f"Bearer {SONAR_TOKEN}"} if SONAR_TOKEN else {}

# Utilities
def exit_with(msg, code=1):
    print(msg)
    sys.exit(code)

def safe_run(cmd, cwd=None, check=True):
    """Run subprocess and print command. Raises CalledProcessError if check and non-zero."""
    print("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)

def run_capture(cmd, cwd=None, check=True):
    """Run subprocess and capture output (stdout/stderr)."""
    print("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 1) Parse input URL
def parse_github_url(url):
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    m_pr = re.match(r"([^/]+)/([^/]+)/pull/(\d+)", path)
    m_commit = re.match(r"([^/]+)/([^/]+)/commit/([0-9a-fA-F]+)", path)
    if m_pr:
        return {"type": "pr", "owner": m_pr.group(1), "repo": m_pr.group(2), "id": m_pr.group(3)}
    elif m_commit:
        return {"type": "commit", "owner": m_commit.group(1), "repo": m_commit.group(2), "id": m_commit.group(3)}
    else:
        exit_with("URL inválida. Forneça uma URL de PR (pull) ou de commit do GitHub.")

# 2) Get changed files + patch (pagination)
def get_pr_files_with_patches(owner, repo, pr_number):
    files = []
    page = 1
    per_page = 100
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=GITHUB_API_HEADERS, params={"page": page, "per_page": per_page})
        if resp.status_code != 200:
            exit_with(f"Erro ao consultar arquivos do PR: {resp.status_code} {resp.text}")
        page_items = resp.json()
        if not page_items:
            break
        files.extend(page_items)
        if len(page_items) < per_page:
            break
        page += 1
    return [f for f in files if f.get("status") != "removed"]

def get_commit_files_with_patches(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    resp = requests.get(url, headers=GITHUB_API_HEADERS)
    if resp.status_code != 200:
        exit_with(f"Erro ao consultar commit: {resp.status_code} {resp.text}")
    data = resp.json()
    return [f for f in data.get("files", []) if f.get("status") != "removed"]

# 3) Extract new-file line numbers from patch (all lines in hunks)
def extract_all_lines_from_patch(patch):
    modified_lines = set()
    if not patch:
        return modified_lines
    for line in patch.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2)) if m.group(2) else 1
                for n in range(start, start + length):
                    modified_lines.add(n)
    return modified_lines

# 4) Checkout/clonar repo seguro
def checkout_pr_or_commit(base_path, owner, repo, kind, identifier):
    repo_url = f"https://github.com/{owner}/{repo}.git"
    repo_path = os.path.join(base_path, repo)
    os.makedirs(base_path, exist_ok=True)

    if not os.path.isdir(repo_path):
        print(f"Clonando {repo_url} em {repo_path} ...")
        safe_run(["git", "clone", repo_url, repo_path])
    else:
        print(f"Repositorio já existe em {repo_path}. Fazendo fetch --all ...")
        safe_run(["git", "fetch", "--all"], cwd=repo_path)

    if kind == "pr":
        pr_num = identifier
        branch_name = f"pr_{pr_num}"
        print(f"Buscando PR {pr_num} em origin (pull/{pr_num}/head -> {branch_name})")
        # If branch is currently checked out, git refuses to fetch into it; we try fetch without target to update refs then fetch target if safe
        # First update remote refs:
        safe_run(["git", "fetch", "origin"], cwd=repo_path, check=False)
        # Then try fetch pr ref into branch (may fail if branch is checked out); ignore failure (we'll checkout afterwards)
        safe_run(["git", "fetch", "origin", f"pull/{pr_num}/head:{branch_name}"], cwd=repo_path, check=False)
    else:
        sha = identifier
        branch_name = f"commit_{sha[:10]}"
        print(f"Criando/Atualizando branch local {branch_name} para o commit {sha}")
        safe_run(["git", "fetch", "origin"], cwd=repo_path, check=False)
        safe_run(["git", "checkout", "-B", branch_name, sha], cwd=repo_path, check=False)

    # check current branch
    try:
        cur = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        current_branch = cur.stdout.strip()
    except Exception:
        current_branch = None

    if current_branch == branch_name:
        print(f"Já estamos na branch {branch_name}")
    else:
        print(f"Tentando checkout seguro para {branch_name} ...")
        safe_run(["git", "checkout", branch_name], cwd=repo_path, check=False)

    # ensure branch exists as fallback
    res = run_capture(["git", "branch", "--list", branch_name], cwd=repo_path)
    if not res.stdout.strip():
        print(f"Atenção: branch {branch_name} não foi criada localmente como esperado. Tentando criar a partir de origin/{branch_name}...")
        safe_run(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"], cwd=repo_path, check=False)

    print(f"Checkout concluído: {repo_path} @ {branch_name}")
    return repo_path, branch_name

# helper: detect if repo looks like a maven/java project
def is_maven_project(repo_path):
    return os.path.isfile(os.path.join(repo_path, "pom.xml"))

def any_java_files(repo_path):
    for root, _, files in os.walk(repo_path):
        for f in files:
            if f.endswith(".java"):
                return True
    return False

# 5) Run sonar via sonar-scanner with Java handling
def run_sonar_analysis(repo_path, branch_name=None):
    print("\n➡ Preparando análise Sonar (sonar-scanner). Aguarde...\n")

    if not SONAR_PROJECT_KEY:
        exit_with("SONAR_PROJECT_KEY não definido. Defina a variável de ambiente SONAR_PROJECT_KEY.")

    props_path = os.path.join(repo_path, "sonar-project.properties")
    sonar_props = {
        "sonar.projectKey": SONAR_PROJECT_KEY,
        "sonar.sources": ".",
        "sonar.host.url": SONAR_URL
    }

    # If Java project (pom.xml) and Maven present -> build
    binaries_path = None
    if is_maven_project(repo_path):
        print("Detectado pom.xml -> projeto Maven/Java. Tentando compilar via Maven...")
        mvn_exec = MAVEN_EXECUTABLE_PATH
        # verify mvn present
        if shutil.which(mvn_exec) is None and not os.path.isfile(mvn_exec):
            # try 'mvn' in PATH as fallback
            if shutil.which("mvn"):
                mvn_exec = "mvn"
            else:
                print("Aviso: Maven não encontrado no caminho configurado. Pulando compilação automática.")
                mvn_exec = None

        if mvn_exec:
            try:
                # run package (skip tests) to produce target/classes
                safe_run([mvn_exec, "clean", "package", "-DskipTests"], cwd=repo_path)
                candidate = os.path.join(repo_path, "target", "classes")
                if os.path.isdir(candidate):
                    binaries_path = "target/classes"
                    print(f"Compilação bem-sucedida. Encontrado: {candidate}")
                else:
                    print("Compilação terminou, mas target/classes não foi encontrado. Continuando com fallback.")
            except subprocess.CalledProcessError as e:
                print("Erro ao executar mvn package. Continuando com fallback (não abortando).")
    else:
        # no pom.xml, but might still contain .java files (e.g. simple project)
        if any_java_files(repo_path):
            print("Encontrados arquivos .java mas sem pom.xml. Será usado fallback (sonar.java.binaries=.) — análise Java será limitada.")
            binaries_path = "."  # fallback

    # write sonar-project.properties if not exists (merge existing minimal)
    if not os.path.exists(props_path):
        print("Criando sonar-project.properties mínimo...")
        lines = []
        for k, v in sonar_props.items():
            lines.append(f"{k}={v}")
        # add Java binaries if we detected one
        if binaries_path:
            lines.append(f"sonar.java.binaries={binaries_path}")
        # if SONAR_TOKEN should be passed
        if SONAR_TOKEN:
            # sonar-scanner accepts sonar.login prop
            lines.append(f"sonar.login={SONAR_TOKEN}")
        content = "\n".join(lines) + "\n"
        with open(props_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Arquivo criado: {props_path}")
    else:
        # if exists, optionally append sonar.java.binaries if not present and we detected binaries_path
        if binaries_path:
            with open(props_path, "r", encoding="utf-8") as f:
                txt = f.read()
            if "sonar.java.binaries" not in txt:
                with open(props_path, "a", encoding="utf-8") as f:
                    f.write(f"\nsonar.java.binaries={binaries_path}\n")
                print("Adicionado sonar.java.binaries ao sonar-project.properties existente.")

    # prepare sonar-scanner command (absolute path if provided)
    if SONAR_SCANNER_PATH:
        cmd = [SONAR_SCANNER_PATH]
    else:
        cmd = ["sonar-scanner"]

    # optionally pass branch name if supported (and if desired)
    if USE_SONAR_BRANCH_NAME and branch_name:
        cmd.append(f"-Dsonar.branch.name={branch_name}")

    # If sonar.login not in properties and we have token, we can pass as env variable or property; but we already added sonar.login to properties above if token present.

    print("Executando sonar-scanner...")
    try:
        proc = subprocess.Popen(cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except FileNotFoundError:
        exit_with("Executável sonar-scanner não encontrado. Defina SONAR_SCANNER_PATH ou coloque sonar-scanner no PATH.")

    # stream output
    for line in proc.stdout:
        print(line, end="")
    stderr = proc.stderr.read()
    if stderr.strip():
        print("\n--- STDERR ---")
        print(stderr)
    proc.wait()
    if proc.returncode != 0:
        exit_with(f"Erro ao rodar sonar-scanner (exit {proc.returncode})")

# 6) Query Sonar issues for components (file-by-file)
def get_sonar_issues_for_components(component_files, branch_name=None):
    if not SONAR_PROJECT_KEY:
        exit_with("SONAR_PROJECT_KEY não definido. Defina a variável de ambiente SONAR_PROJECT_KEY.")

    issues_all = []
    for file_path in component_files:
        component_key = f"{SONAR_PROJECT_KEY}:{file_path}"
        params = {
            "componentKeys": component_key,
            "types": "BUG,VULNERABILITY,CODE_SMELL",
            "resolved": "false",
            "ps": "500"
        }
        if USE_SONAR_BRANCH_NAME and branch_name:
            params["branch"] = branch_name
        url = f"{SONAR_URL}/api/issues/search"
        resp = requests.get(url, headers=SONAR_API_HEADERS, params=params)
        if resp.status_code != 200:
            print(f"Warning: erro ao consultar Sonar para {file_path}: {resp.status_code} {resp.text}")
            continue
        data = resp.json()
        issues_all.extend(data.get("issues", []))
    return issues_all

# 7) Filter issues by files and modified lines
def filter_issues_by_diff(issues, changed_files_lines_map):
    filtered = []
    for issue in issues:
        comp = issue.get("component", "")
        file_path = comp.split(":", 1)[-1] if ":" in comp else comp
        line = issue.get("line")
        if line is None:
            continue
        modified_lines = changed_files_lines_map.get(file_path, set())
        if line in modified_lines:
            filtered.append(issue)
    return filtered

# 8) Report generation (saved in script dir)
def generate_report(pr_or_commit_url, kind, identifier, branch_name, changed_files_lines_map, filtered_issues):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"sonar_report_{kind}_{identifier}_{timestamp}.txt"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, out_name)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"RELATÓRIO SONAR - FILTRADO POR DIFF\n")
        f.write(f"Origem: {pr_or_commit_url}\n")
        f.write(f"Tipo: {kind}\n")
        f.write(f"Ref/ID: {identifier}\n")
        f.write(f"Branch usada: {branch_name}\n")
        f.write(f"Data: {timestamp}\n")
        f.write("="*80 + "\n\n")
        f.write("Arquivos alterados e linhas modificadas (amostra):\n")
        for fp, lines in changed_files_lines_map.items():
            f.write(f"- {fp}: {sorted(list(lines))[:20]}{' ...' if len(lines)>20 else ''}\n")
        f.write("\n")
        f.write(f"Total de issues (após filtro por linha): {len(filtered_issues)}\n\n")
        for issue in filtered_issues:
            file_path = issue['component'].split(':', 1)[-1]
            f.write("-"*40 + "\n")
            f.write(f"Arquivo: {file_path}\n")
            f.write(f"Linha: {issue.get('line')}\n")
            f.write(f"Tipo: {issue.get('type')} ({issue.get('severity')})\n")
            f.write(f"Mensagem: {issue.get('message')}\n")
            f.write(f"Key: {issue.get('key')}\n")
            f.write(f"Link: {SONAR_URL}/project/issues?id={SONAR_PROJECT_KEY}&issues={issue.get('key')}\n")
        f.write("\n" + "="*80 + "\n")
    print(f"\n✅ Relatório gerado: {output_file}")

# Main
def main():
    if len(sys.argv) < 2:
        exit_with("Uso: python analise_sonar.py <url_do_pr_ou_commit>")

    url = sys.argv[1]
    parsed = parse_github_url(url)
    kind = parsed["type"]
    owner = parsed["owner"]
    repo = parsed["repo"]
    identifier = parsed["id"]

    print(f"Kind: {kind}, Repo: {owner}/{repo}, ID: {identifier}")

    if kind == "pr":
        raw_files = get_pr_files_with_patches(owner, repo, identifier)
    else:
        raw_files = get_commit_files_with_patches(owner, repo, identifier)

    if not raw_files:
        exit_with("Nenhum arquivo alterado encontrado no PR/commit.")

    changed_files_lines_map = {}
    changed_file_list = []
    for item in raw_files:
        filename = item.get("filename")
        patch = item.get("patch", "")
        lines_set = extract_all_lines_from_patch(patch)
        changed_files_lines_map[filename] = lines_set
        changed_file_list.append(filename)
        print(f"Arquivo: {filename}, linhas modificadas: {len(lines_set)}")

    try:
        repo_path, branch_name = checkout_pr_or_commit(BASE_REPOS_PATH, owner, repo, kind, identifier)
    except subprocess.CalledProcessError as e:
        exit_with(f"Erro git ao dar checkout: {e}")

    # run sonar-scanner (with java handling)
    try:
        run_sonar_analysis(repo_path, branch_name if USE_SONAR_BRANCH_NAME else None)
    except Exception as e:
        exit_with(f"Erro ao executar Sonar Scanner: {e}")

    # query sonar issues
    try:
        sonar_issues = get_sonar_issues_for_components(changed_file_list, branch_name if USE_SONAR_BRANCH_NAME else None)
    except Exception as e:
        exit_with(f"Erro ao consultar Sonar: {e}")

    print(f"Total de issues retornadas pelo Sonar (em arquivos alterados): {len(sonar_issues)}")

    filtered_issues = filter_issues_by_diff(sonar_issues, changed_files_lines_map)
    print(f"Issues após filtro por linhas do diff: {len(filtered_issues)}")

    generate_report(url, kind, identifier, branch_name, changed_files_lines_map, filtered_issues)

if __name__ == "__main__":
    main()
