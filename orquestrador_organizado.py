import os
import glob
import subprocess
import sys
import time
import shutil

# --- CONFIGURAÇÃO DE DIRETÓRIOS DE SAÍDA ---
# Onde ficarão os JSONs gerados pelo Gemini (main.py)
DIR_OUTPUT_LLM = "saida_analise_llm"
# Onde ficarão os relatórios consolidados do Sonar
DIR_OUTPUT_SONAR_GERAL = "saida_sonar_consolidado"
# Onde ficarão os JSONs individuais de cada PR analisado pelo Sonar
DIR_OUTPUT_SONAR_DETALHES = "saida_sonar_detalhes"

def ensure_directories():
    """Cria os diretórios de organização se não existirem."""
    for folder in [DIR_OUTPUT_LLM, DIR_OUTPUT_SONAR_GERAL, DIR_OUTPUT_SONAR_DETALHES]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Diretório criado: {folder}")

def run_command(command, env_vars=None):
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    try:
        subprocess.run(command, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Erro ao executar comando: {e}")
        raise # Relança erro para controle de fluxo

def get_latest_file(pattern):
    """Retorna o arquivo mais recente que corresponde ao padrão."""
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def main():
    print("========================================================")
    print("🚀 INICIANDO ORQUESTRADOR COM SAÍDAS ORGANIZADAS")
    print("========================================================\n")
    
    ensure_directories()
    
    # ---------------------------------------------------------
    # ETAPA 1: Executar main.py e organizar saída (LLM)
    # ---------------------------------------------------------
    repo_files = sorted(glob.glob("repositorio*.json"))
    
    generated_llm_files = []

    if not repo_files:
        print("⚠️ Nenhum arquivo 'repositorio*.json' encontrado.")
    else:
        for repo_file in repo_files:
            print(f"\n🔹 Processando LLM para configuração: {repo_file}")
            
            # 1. Registra arquivos existentes para saber qual é o novo
            existing_files = set(glob.glob("pr_info_final_*.json"))
            
            # 2. Executa a análise
            env_vars = {"REPOS_FILE": repo_file}
            try:
                run_command([sys.executable, "main.py"], env_vars=env_vars)
            except:
                print(f"   ⚠️ Pulo o arquivo {repo_file} devido a erro.")
                continue

            # 3. Identifica o arquivo novo gerado
            current_files = set(glob.glob("pr_info_final_*.json"))
            new_files = current_files - existing_files
            
            if new_files:
                # Pega o arquivo recém-criado
                new_json = list(new_files)[0]
                
                # Define nome de destino mais organizado (ex: llm_result_repositorio_java.json)
                base_name = os.path.basename(repo_file).replace('.json', '')
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                dest_name = f"llm_result_{base_name}_{timestamp}.json"
                dest_path = os.path.join(DIR_OUTPUT_LLM, dest_name)
                
                # Move o arquivo para a pasta organizada
                shutil.move(new_json, dest_path)
                print(f"   ✅ Arquivo gerado e movido para: {dest_path}")
                generated_llm_files.append(dest_path)
            else:
                print("   ⚠️ O script main.py rodou, mas não gerou arquivo novo na raiz.")

    print("\n--------------------------------------------------------")
    print("✅ Análise LLM concluída. Iniciando SonarScanner...")
    print("--------------------------------------------------------\n")

    # ---------------------------------------------------------
    # ETAPA 2: Executar SonarScanner para os arquivos organizados
    # ---------------------------------------------------------
    # Se rodou a etapa 1 agora, usa a lista generated_llm_files. 
    # Caso contrário, pega tudo que estiver na pasta de saída da LLM para processar.
    if not generated_llm_files:
        generated_llm_files = sorted(glob.glob(os.path.join(DIR_OUTPUT_LLM, "*.json")))

    if not generated_llm_files:
        print(f"⚠️ Nenhum arquivo encontrado em {DIR_OUTPUT_LLM} para scan.")
    else:
        for llm_file in generated_llm_files:
            print(f"\n📡 Executando SonarScanner sobre: {llm_file}")
            
            # Cria nome único para o relatório consolidado deste lote
            base_name = os.path.basename(llm_file).replace('.json', '')
            consolidated_name = f"sonar_report_{base_name}.json"
            consolidated_path = os.path.join(DIR_OUTPUT_SONAR_GERAL, consolidated_name)
            
            # Define subpasta específica para os detalhes deste arquivo (para não misturar)
            details_dir = os.path.join(DIR_OUTPUT_SONAR_DETALHES, base_name)
            
            # Configura variáveis de ambiente que o sonnar-scanner.py aceita 
            env_vars = {
                "INPUT_FILE": llm_file,
                "OUTPUT_FILE": consolidated_path,
                "RESULTS_DIR": details_dir
            }
            
            run_command([sys.executable, "sonnar-scanner.py"], env_vars=env_vars)
            print(f"   📄 Relatório consolidado: {consolidated_path}")
            print(f"   📂 Detalhes individuais em: {details_dir}")

    print("\n========================================================")
    print("🏁 PROCESSO FINALIZADO")
    print(f"📂 LLM Output:    ./{DIR_OUTPUT_LLM}")
    print(f"📂 Sonar Report:  ./{DIR_OUTPUT_SONAR_GERAL}")
    print(f"📂 Sonar Details: ./{DIR_OUTPUT_SONAR_DETALHES}")
    print("========================================================")

if __name__ == "__main__":
    main()