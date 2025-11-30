"""

Uso:
    python analise_sonar.py <url_do_pr_ou_commit>

Ex:
    python analise_sonar.py https://github.com/FasterXML/jackson-databind/pull/5317
    python analise_sonar.py https://github.com/fulano/repo/commit/abcdef123456
"""
import re
import os
import sys
import subprocess
from datetime import datetime
from urllib.parse import urlparse
import requests

try:
    from llm_code_reviewer import config
    GITHUB_TOKEN = config.GITHUB_TOKEN
except Exception:
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

SONAR_TOKEN = os.environ.get("SONAR_TOKEN")
SONAR_URL = "http://localhost:9000"
SONAR_PROJECT_KEY = os.environ.get("SONAR_PROJECT_KEY")
MAVEN_EXECUTABLE_PATH = r"C:\Program Files\apache-maven-3.9.9\bin\mvn.cmd"

BASE_REPOS_PATH = os.environ.get("BASE_REPOS_PATH", r"C:\workspace\llm-test")

USE_SONAR_BRANCH_NAME = False

# Headers para GitHub / Sonar
GITHUB_API_HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {"Accept": "application/vnd.github.v3+json"}
SONAR_API_HEADERS = {"Authorization": f"Bearer {SONAR_TOKEN}"} if SONAR_TOKEN else {}

# Utilities -----------------------------------------------------------------
def exit_with(msg, code=1):
    print(msg)
    sys.exit(code)

def safe_run(cmd, cwd=None, check=True):
    """Run subprocess and print command. Raises CalledProcessError if check and non-zero."""
    print("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)

def run_capture(cmd, cwd=None, check=True):
    """Run subprocess and capture output (stdout/stderr). Returns CompletedProcess."""
    print("> " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 1) Parse input URL -------------------------------------------------------
def parse_github_url(url):
    """
    Retorna um dict com tipo: 'pr' ou 'commit', owner, repo, id
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    # exemplos:
    # owner/repo/pull/5317
    # owner/repo/commit/abcdef
    m_pr = re.match(r"([^/]+)/([^/]+)/pull/(\d+)", path)
    m_commit = re.match(r"([^/]+)/([^/]+)/commit/([0-9a-fA-F]+)", path)
    if m_pr:
        return {"type": "pr", "owner": m_pr.group(1), "repo": m_pr.group(2), "id": m_pr.group(3)}
    elif m_commit:
        return {"type": "commit", "owner": m_commit.group(1), "repo": m_commit.group(2), "id": m_commit.group(3)}
    else:
        exit_with("URL inválida. Forneça uma URL de PR (pull) ou de commit do GitHub.")

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
    # filtra removidos
    return [f for f in files if f.get("status") != "removed"]

def get_commit_files_with_patches(owner, repo, sha):
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    resp = requests.get(url, headers=GITHUB_API_HEADERS)
    if resp.status_code != 200:
        exit_with(f"Erro ao consultar commit: {resp.status_code} {resp.text}")
    data = resp.json()
    return [f for f in data.get("files", []) if f.get("status") != "removed"]

def extract_all_lines_from_patch(patch):
    """
    Retorna um set com TODAS as linhas do arquivo 'novo' presentes no diff,
    extraindo os ranges +start,length de cada hunk.
    """
    modified_lines = set()
    if not patch:
        return modified_lines

    for line in patch.splitlines():
        if line.startswith("@@"):
            # Ex: @@ -184,7 +184,7 @@
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2)) if m.group(2) else 1
                for n in range(start, start + length):
                    modified_lines.add(n)
    return modified_lines

# 4) Checkout/clonar repo seguro -------------------------------------------
def checkout_pr_or_commit(base_path, owner, repo, kind, identifier):
    """
    Garantias:
      - clona o repo em base_path/<repo> se não existir
      - se existir, faz fetch --all
      - para PRs, faz fetch origin pull/<n>/head:pr_<n> e faz checkout seguro
      - para commits, cria/atualiza branch local short_<sha> e faz checkout
    Retorna: (repo_path, branch_name_used)
    """
    repo_url = f"https://github.com/{owner}/{repo}.git"
    repo_path = os.path.join(base_path, repo)

    os.makedirs(base_path, exist_ok=True)

    # 1) clone se necessário
    if not os.path.isdir(repo_path):
        print(f"Clonando {repo_url} em {repo_path} ...")
        safe_run(["git", "clone", repo_url, repo_path])
    else:
        print(f"Repositorio já existe em {repo_path}. Fazendo fetch --all ...")
        safe_run(["git", "fetch", "--all"], cwd=repo_path)

    # 2) preparar branch_name e fetch especial se PR
    if kind == "pr":
        pr_num = identifier
        branch_name = f"pr_{pr_num}"

        # fetch a ref do PR para a branch local (cria/atualiza pr_<n>)
        print(f"Buscando PR {pr_num} em origin (pull/{pr_num}/head -> {branch_name})")
        # check: fetch may fail if remote doesn't allow, but check=False avoids raising
        safe_run(["git", "fetch", "origin", f"pull/{pr_num}/head:{branch_name}"], cwd=repo_path, check=False)

    else:
        # commit
        sha = identifier
        # criar um branch local que referencia o SHA para facilitar o checkout e sonar run
        branch_name = f"commit_{sha[:10]}"
        print(f"Criando/Atualizando branch local {branch_name} para o commit {sha}")
        safe_run(["git", "fetch", "origin"], cwd=repo_path, check=False)
        # create or move branch to the commit sha
        safe_run(["git", "checkout", "-B", branch_name, sha], cwd=repo_path, check=False)

    # 3) verificar se já estamos nessa branch
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

    # 4) garantir que a branch local existe (como fallback)
    res = run_capture(["git", "branch", "--list", branch_name], cwd=repo_path)
    if not res.stdout.strip():
        print(f"Atenção: branch {branch_name} não foi criada localmente como esperado. Tentando reset remoto...")
        # tenta criar a partir de origin/branch_name (caso exista)
        safe_run(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"], cwd=repo_path, check=False)

    print(f"Checkout concluído: {repo_path} @ {branch_name}")
    return repo_path, branch_name

def run_sonar_analysis(repo_path, branch_name=None):
    """
    Executa mvn sonar:sonar no repo_path. Se USE_SONAR_BRANCH_NAME True e branch_name fornecido,
    passa -Dsonar.branch.name.
    """
    print("\n➡ Iniciando análise Sonar (Maven). Aguarde...\n")
    maven_command = [
        MAVEN_EXECUTABLE_PATH,
        "clean", "install", "-DskipTests",
        "sonar:sonar",
        f"-Dsonar.projectKey={SONAR_PROJECT_KEY}",
        f"-Dsonar.host.url={SONAR_URL}",
        f"-Dsonar.token={SONAR_TOKEN}"
    ]
    if USE_SONAR_BRANCH_NAME and branch_name:
        maven_command.append(f"-Dsonar.branch.name={branch_name}")

    proc = subprocess.Popen(maven_command, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    for line in proc.stdout:
        print(line, end="")
    stderr_output = proc.stderr.read()
    if stderr_output:
        print("\n--- STDERR ---")
        print(stderr_output)
    proc.wait()
    if proc.returncode != 0:
        exit_with(f"Erro: Maven/sonar:sonar retornou código {proc.returncode}")

def get_sonar_issues_for_components(component_files, branch_name=None):
    """
    Agora consulta um arquivo por vez para evitar o erro:
    "All components must have the same qualifier (FIL,UTS)"
    """
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
            exit_with(f"Erro ao consultar Sonar para {file_path}: {resp.status_code} {resp.text}")

        data = resp.json()
        issues_all.extend(data.get("issues", []))

    return issues_all


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

    # 3) prepare checkout/clone
    try:
        repo_path, branch_name = checkout_pr_or_commit(BASE_REPOS_PATH, owner, repo, kind, identifier)
    except subprocess.CalledProcessError as e:
        exit_with(f"Erro git ao dar checkout: {e}")

    # 4) run sonar (no repo_path). se USE_SONAR_BRANCH_NAME False não passamos branch
    try:
        run_sonar_analysis(repo_path, branch_name if USE_SONAR_BRANCH_NAME else None)
    except Exception as e:
        exit_with(f"Erro ao executar Sonar/Maven: {e}")

    # 5) query Sonar issues for changed files
    try:
        sonar_issues = get_sonar_issues_for_components(changed_file_list, branch_name if USE_SONAR_BRANCH_NAME else None)
    except Exception as e:
        exit_with(f"Erro ao consultar Sonar: {e}")

    print(f"Total de issues retornadas pelo Sonar (em arquivos alterados): {len(sonar_issues)}")

    # 6) filter by modified lines
    filtered_issues = filter_issues_by_diff(sonar_issues, changed_files_lines_map)
    print(f"Issues após filtro por linhas do diff: {len(filtered_issues)}")

    # 7) generate report (no diretório do script)
    generate_report(url, kind, identifier, branch_name, changed_files_lines_map, filtered_issues)

if __name__ == "__main__":
    main()
