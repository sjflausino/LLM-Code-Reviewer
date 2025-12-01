import json
import os
import subprocess
import shutil
import time
import requests
import sys
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURAÇÕES ---
SONAR_HOST_URL = os.getenv('SONAR_HOST_URL', 'http://localhost:9000')
SONAR_TOKEN = os.getenv('SONAR_TOKEN')
SONAR_LOGIN = os.getenv('SONAR_LOGIN')
SONAR_PASSWORD = os.getenv('SONAR_PASSWORD')

INPUT_FILE = os.getenv('INPUT_FILE', 'pr_info_final_20251130_162706_v1.json')
OUTPUT_FILE = os.getenv('OUTPUT_FILE', 'relatorio_sonar_detalhado.json')
TEMP_DIR = 'temp_repos'

# Métricas
METRIC_KEYS = "bugs,vulnerabilities,code_smells,sqale_index,coverage,duplicated_lines_density"

# Helper de Autenticação para requests
def get_auth():
    if SONAR_TOKEN:
        return (SONAR_TOKEN, '')
    elif SONAR_LOGIN and SONAR_PASSWORD:
        return (SONAR_LOGIN, SONAR_PASSWORD)
    return None

def run_command(command, cwd=None):
    try:
        # shell=True permite usar && e pipes se necessário, mas aqui executamos comando direto
        result = subprocess.run(
            command, 
            cwd=cwd, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ.copy()
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # print(f"Erro no comando: {e.stderr}") # Descomente para debug
        return None

def get_sonar_analysis_status(ce_task_id):
    url = f"{SONAR_HOST_URL}/api/ce/task?id={ce_task_id}"
    auth = get_auth()
    
    print(f"   ⏳ Aguardando Compute Engine (Task: {ce_task_id})...")
    
    for _ in range(60): 
        try:
            response = requests.get(url, auth=auth)
            if response.status_code != 200: return None
            
            data = response.json()
            task = data['task']
            
            if task['status'] == 'SUCCESS': return task['analysisId']
            elif task['status'] in ['FAILED', 'CANCELED']:
                print(f"   ❌ Falha: {task.get('errorMessage', '')}")
                return None
            time.sleep(2)
        except: time.sleep(2)
    return None

def get_sonar_measures(component_key):
    url = f"{SONAR_HOST_URL}/api/measures/component"
    params = {'component': component_key, 'metricKeys': METRIC_KEYS}
    auth = get_auth()
    try:
        r = requests.get(url, params=params, auth=auth)
        if r.status_code == 200:
            measures = {}
            for m in r.json().get('component', {}).get('measures', []):
                measures[m['metric']] = m['value']
            return measures
    except: pass
    return {}

def get_sonar_issues_details(component_key):
    url = f"{SONAR_HOST_URL}/api/issues/search"
    auth = get_auth()
    all_issues = []
    page = 1
    
    while True:
        params = {
            'componentKeys': component_key,
            'types': 'CODE_SMELL,VULNERABILITY',
            'ps': 500,
            'p': page,
            'additionalFields': '_all'
        }
        try:
            r = requests.get(url, params=params, auth=auth)
            if r.status_code != 200: break
            data = r.json()
            issues = data.get('issues', [])
            if not issues: break
            
            for issue in issues:
                all_issues.append({
                    "type": issue.get('type'),
                    "severity": issue.get('severity'),
                    "rule": issue.get('rule'),
                    "message": issue.get('message'),
                    "file": issue.get('component', '').split(':')[-1],
                    "line": issue.get('line', 0),
                    "effort": issue.get('effort', '')
                })
            
            if page * 500 >= data.get('paging', {}).get('total', 0): break
            page += 1
        except: break
    return all_issues

def analyze_pr(owner, repo_name, pr_number):
    repo_url = f"https://github.com/{owner}/{repo_name}.git"
    
    # Gera uma chave única: owner_repo_pr1
    project_key = f"{owner}_{repo_name}_pr{pr_number}".replace("-", "_").replace(".", "_")
    
    # Diretório temporário
    base_dir = os.path.join(TEMP_DIR, f"{owner}_{repo_name}_{pr_number}")
    
    print(f"\n--- {owner}/{repo_name} PR #{pr_number} ---")

    # Limpeza e criação do diretório
    if os.path.exists(base_dir): shutil.rmtree(base_dir)
    os.makedirs(base_dir)

    # 1. Clone e Checkout (Equivalente ao seu git fetch && git switch)
    print(f"   📥 Baixando código...")
    
    # Clone sem checkout inicial para ganhar tempo
    run_command(f"git clone -n {repo_url} .", cwd=base_dir) 
    
    # Fetch do PR específico para uma branch local chamada 'pr-branch'
    run_command(f"git fetch origin pull/{pr_number}/head:pr-branch", cwd=base_dir)
    
    # Switch para a branch
    run_command(f"git switch pr-branch", cwd=base_dir)

    print(f"   🔍 Analisando...")
    
    # Montagem do comando SonarScanner
    sonar_args = [
        "sonar-scanner",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.projectName=\"{owner}/{repo_name} PR #{pr_number}\"",
        f"-Dsonar.sources=.",
        f"-Dsonar.host.url={SONAR_HOST_URL}",
        f"-Dsonar.scm.disabled=true"
    ]

    # Decide qual autenticação usar
    if SONAR_TOKEN:
        sonar_args.append(f"-Dsonar.token={SONAR_TOKEN}")
    elif SONAR_LOGIN and SONAR_PASSWORD:
        sonar_args.append(f"-Dsonar.login={SONAR_LOGIN}")
        sonar_args.append(f"-Dsonar.password={SONAR_PASSWORD}")
    
    # Junta os argumentos em uma string para execução
    sonar_cmd = " ".join(sonar_args)
    
    run_command(sonar_cmd, cwd=base_dir)

    # Coleta de resultados
    report_task_path = os.path.join(base_dir, '.scannerwork', 'report-task.txt')
    results = {"metrics": {}, "issues": []}
    
    if os.path.exists(report_task_path):
        with open(report_task_path, 'r') as f:
            ce_task_id = next((l.split('=')[1].strip() for l in f if l.startswith('ceTaskId=')), None)
            
        if ce_task_id and get_sonar_analysis_status(ce_task_id):
            print("   ✅ Coletando detalhes...")
            results["metrics"] = get_sonar_measures(project_key)
            results["issues"] = get_sonar_issues_details(project_key)
        else:
            print("   ⚠️ Erro na análise do servidor.")
    else:
        print("   ⚠️ Report do Sonar não encontrado. O scanner rodou?")
    
    shutil.rmtree(base_dir)
    return results

def main():
    # Verifica se existe arquivo de entrada
    if not os.path.exists(INPUT_FILE):
        print(f"❌ ERRO: Arquivo de entrada '{INPUT_FILE}' não encontrado.")
        return
    
    # Verifica autenticação
    if not SONAR_TOKEN and not (SONAR_LOGIN and SONAR_PASSWORD):
        print("❌ ERRO: Configure SONAR_TOKEN ou (SONAR_LOGIN e SONAR_PASSWORD) no .env")
        return

    print(f"⚙️  Sonar URL: {SONAR_HOST_URL}")
    print(f"📂 Lendo: {INPUT_FILE}")

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    output_data = {
        "run_summary": {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "tool": "SonarScanner Automation"},
        "repositories": []
    }

    for repo in data.get('repositories', []):
        owner, repo_name = repo['owner'], repo['repo']
        repo_entry = {"owner": owner, "repo": repo_name, "pull_requests": []}

        for pr in repo.get('pull_requests', []):
            res = analyze_pr(owner, repo_name, pr['pr_number'])
            repo_entry["pull_requests"].append({
                "pr_number": pr['pr_number'],
                "title": pr.get('title', ''),
                "url": pr.get('url', ''),
                "sonar_results": {"summary_metrics": res["metrics"], "detected_issues": res["issues"]}
            })
        output_data["repositories"].append(repo_entry)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Relatório salvo em: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()