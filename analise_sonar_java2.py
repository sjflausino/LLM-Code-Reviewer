"""
Uso:
    python analise_sonar_batch.py <caminho_do_arquivo_json>

O arquivo JSON deve seguir o formato:
[
  {
    "owner": "FasterXML",
    "repo": "jackson-databind",
    "url": "...",
    "pull_requests": [5325, 5397]
  },
  {
    "owner": "spring-cloud",
    "repo": "spring-cloud-function",
    "commits": [
       {"commit_hash": "2aed5abff8d755a87bbdb2423cbd154e0c33c4ad"}
    ]
  }
]
"""
import re
import os
import sys
import subprocess
import json
from datetime import datetime
import requests

try:
    from llm_code_reviewer import config
    GITHUB_TOKEN = config.GITHUB_TOKEN
except Exception:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Configurações Sonar
SONAR_TOKEN = os.environ.get("SONAR_TOKEN")
SONAR_URL = "http://localhost:9000"
# Se não definido, geraremos dinamicamente owner_repo
DEFAULT_SONAR_PROJECT_KEY = os.environ.get("SONAR_PROJECT_KEY") 

MAVEN_EXECUTABLE_PATH = r"C:\Program Files\apache-maven-3.9.11\bin\mvn.cmd"
BASE_REPOS_PATH = os.environ.get("BASE_REPOS_PATH", r"C:\workspace\llm-test")
REPORTS_DIR = "sonar_reports"

USE_SONAR_BRANCH_NAME = False

# Headers
GITHUB_API_HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {"Accept": "application/vnd.github.v3+json"}
SONAR_API_HEADERS = {"Authorization": f"Bearer {SONAR_TOKEN}"} if SONAR_TOKEN else {}

# Utilities -----------------------------------------------------------------
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def safe_run(cmd, cwd=None, check=True):
    log("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)

def run_capture(cmd, cwd=None, check=True):
    log("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 1) GitHub API Interactions ------------------------------------------------
def get_pr_files_with_patches(owner, repo, pr_number):
    files = []
    page = 1
    per_page = 100
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        resp = requests.get(url, headers=GITHUB_API_HEADERS, params={"page": page, "per_page": per_page})
        if resp.status_code != 200:
            raise Exception(f"Erro ao consultar arquivos do PR {pr_number}: {resp.status_code} {resp.text}")
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
        raise Exception(f"Erro ao consultar commit {sha}: {resp.status_code} {resp.text}")
    data = resp.json()
    return [f for f in data.get("files", []) if f.get("status") != "removed"]

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

# 2) Git Operations --------------------------------------------------------
def checkout_pr_or_commit(base_path, owner, repo, kind, identifier):
    repo_url = f"https://github.com/{owner}/{repo}.git"
    repo_path = os.path.join(base_path, repo)
    os.makedirs(base_path, exist_ok=True)

    if not os.path.isdir(repo_path):
        log(f"Clonando {repo_url} em {repo_path} ...")
        safe_run(["git", "clone", repo_url, repo_path])
    else:
        log(f"Repositorio já existe. Fetching...")
        safe_run(["git", "fetch", "--all"], cwd=repo_path)

    if kind == "pr":
        pr_num = identifier
        branch_name = f"pr_{pr_num}"
        log(f"Buscando PR {pr_num} -> {branch_name}")
        safe_run(["git", "fetch", "origin", f"pull/{pr_num}/head:{branch_name}"], cwd=repo_path, check=False)
    else:
        sha = identifier
        branch_name = f"commit_{sha[:10]}"
        log(f"Preparando branch para commit {sha}")
        safe_run(["git", "fetch", "origin"], cwd=repo_path, check=False)
        safe_run(["git", "checkout", "-B", branch_name, sha], cwd=repo_path, check=False)

    # Verifica branch atual
    try:
        cur = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        current_branch = cur.stdout.strip()
    except Exception:
        current_branch = None

    if current_branch != branch_name:
        safe_run(["git", "checkout", branch_name], cwd=repo_path, check=False)

    return repo_path, branch_name

# 3) Sonar Analysis --------------------------------------------------------
def run_sonar_analysis(repo_path, project_key, branch_name=None):
    log(f"Iniciando análise Sonar (Key={project_key})...")
    
    maven_command = [
        MAVEN_EXECUTABLE_PATH,
        "clean", "install", "-DskipTests",
        "-Dgpg.skip",
        "-Dmaven.javadoc.skip=true"
        "sonar:sonar",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName={project_key}",
        f"-Dsonar.host.url={SONAR_URL}",
        f"-Dsonar.token={SONAR_TOKEN}"
    ]
    if USE_SONAR_BRANCH_NAME and branch_name:
        maven_command.append(f"-Dsonar.branch.name={branch_name}")

    maven_cwd = repo_path
    if not os.path.exists(os.path.join(repo_path, "pom.xml")):
        for root, dirs, files in os.walk(repo_path):
            if "pom.xml" in files:
                maven_cwd = root
                break

    # Inicia o processo
    proc = subprocess.Popen(maven_command, cwd=maven_cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    
    # --- ALTERAÇÃO AQUI: Loop para imprimir em tempo real ---
    # Lê stdout linha a linha e imprime
    for line in proc.stdout:
        print(line, end="")
    
    # Lê o restante do stderr (erros) e espera o processo terminar
    stderr_output = proc.stderr.read()
    proc.wait()
    # --------------------------------------------------------
    
    if proc.returncode != 0:
        log("STDERR Sonar:\n" + stderr_output)
        raise Exception(f"Maven retornou código {proc.returncode}")

def get_sonar_issues_for_components(project_key, component_files, branch_name=None):
    issues_all = []
    # Consultar em batches ou um a um
    for file_path in component_files:
        component_key = f"{project_key}:{file_path}"
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
        
        # Se 404, pode ser que o arquivo não tenha issues ou path mudou, ignorar mas logar
        if resp.status_code == 404:
            continue 
        if resp.status_code != 200:
            log(f"Erro Sonar API ({file_path}): {resp.status_code}")
            continue

        data = resp.json()
        issues_all.extend(data.get("issues", []))
    return issues_all

def filter_issues_by_diff(issues, changed_files_lines_map, project_key):
    filtered = []
    for issue in issues:
        comp = issue.get("component", "")
        # Remove a chave do projeto do início do component key
        # Ex: "FasterXML_jackson-databind:src/main/java/..." -> "src/main/java/..."
        file_path = comp.replace(f"{project_key}:", "")
        
        line = issue.get("line")
        if line is None:
            continue
        
        modified_lines = changed_files_lines_map.get(file_path, set())
        if line in modified_lines:
            filtered.append(issue)
    return filtered

# 4) Report ----------------------------------------------------------------
def generate_report(owner, repo, kind, identifier, branch_name, changed_files_lines_map, filtered_issues, duration, output_dir):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_identifier = str(identifier).replace("/", "_")
    out_name = f"{owner}_{repo}_{kind}_{safe_identifier}_{timestamp}.txt"
    output_file = os.path.join(output_dir, out_name)

    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"RELATÓRIO SONAR - {owner}/{repo}\n")
        f.write(f"Tipo: {kind} | ID: {identifier}\n")
        f.write(f"Branch: {branch_name}\n")
        f.write(f"Duração análise: {duration}\n")
        f.write("="*80 + "\n\n")

        f.write("Arquivos alterados (amostra de linhas):\n")
        for fp, lines in changed_files_lines_map.items():
            f.write(f"- {fp}: {sorted(list(lines))[:15]}...\n")
        f.write("\n")
        f.write(f"Issues Encontradas (Diff Context): {len(filtered_issues)}\n\n")

        for issue in filtered_issues:
            f.write("-" * 40 + "\n")
            f.write(f"Arquivo: {issue['component'].split(':', 1)[-1]}\n")
            f.write(f"Linha: {issue.get('line')} | Severidade: {issue.get('severity')}\n")
            f.write(f"Msg: {issue.get('message')}\n")
            f.write(f"Rule: {issue.get('rule')}\n")
    
    log(f"✅ Relatório salvo em: {output_file}")

# 5) Core Logic per Item ---------------------------------------------------
def process_single_item(owner, repo, kind, identifier):
    """
    Executa todo o fluxo para um único PR ou Commit.
    """
    try:
        log(f"\n--- Processando {owner}/{repo} -> {kind} {identifier} ---")
        
        # 1. Obter arquivos alterados e linhas
        if kind == "pr":
            raw_files = get_pr_files_with_patches(owner, repo, identifier)
        else:
            raw_files = get_commit_files_with_patches(owner, repo, identifier)

        if not raw_files:
            log("⚠ Nenhum arquivo alterado/patch encontrado. Pulando.")
            return

        changed_files_lines_map = {}
        changed_file_list = []
        for item in raw_files:
            filename = item.get("filename")
            patch = item.get("patch", "")
            lines_set = extract_all_lines_from_patch(patch)
            if lines_set: # Só nos importa se houve mudança de linhas de código
                changed_files_lines_map[filename] = lines_set
                changed_file_list.append(filename)

        if not changed_file_list:
            log("⚠ Arquivos alterados detectados, mas sem diff de linhas legível. Pulando.")
            return

        # 2. Checkout
        repo_path, branch_name = checkout_pr_or_commit(BASE_REPOS_PATH, owner, repo, kind, identifier)

        # 3. Definir Project Key (Único por repo para não misturar análises)
        project_key = DEFAULT_SONAR_PROJECT_KEY if DEFAULT_SONAR_PROJECT_KEY else f"{owner}_{repo}"
        # Sanitizar chave (sonar não gosta de espaços ou chars especiais)
        project_key = re.sub(r'[^a-zA-Z0-9\-_]', '_', project_key)

        # 4. Rodar Sonar
        start_time = datetime.now()
        run_sonar_analysis(repo_path, project_key, branch_name if USE_SONAR_BRANCH_NAME else None)
        end_time = datetime.now()

        # 5. Consultar Issues e Filtrar
        sonar_issues = get_sonar_issues_for_components(project_key, changed_file_list, branch_name if USE_SONAR_BRANCH_NAME else None)
        filtered_issues = filter_issues_by_diff(sonar_issues, changed_files_lines_map, project_key)

        # 6. Gerar Relatório
        generate_report(
            owner, repo, kind, identifier, branch_name, 
            changed_files_lines_map, filtered_issues, 
            end_time - start_time, REPORTS_DIR
        )

    except Exception as e:
        log(f"❌ Erro ao processar {kind} {identifier}: {e}")
        # Não damos exit_with aqui para permitir que o loop continue para o próximo item

def main():
    if len(sys.argv) < 2:
        print("Uso: python analise_sonar_java.py <arquivo_entrada.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not os.path.exists(json_path):
        print(f"Arquivo não encontrado: {json_path}")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Cria diretório de output
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Itera sobre a lista de repos
    for entry in data:
        owner = entry.get("owner")
        repo = entry.get("repo")
        
        # Processar Pull Requests
        prs = entry.get("pull_requests", [])
        if prs:
            for pr_id in prs:
                process_single_item(owner, repo, "pr", pr_id)

        # Processar Commits
        commits = entry.get("commits", [])
        if commits:
            for commit_obj in commits:
                c_hash = commit_obj.get("commit_hash")
                if c_hash:
                    process_single_item(owner, repo, "commit", c_hash)

    log("\n🏁 Processamento em lote finalizado.")

if __name__ == "__main__":
    main()