import pandas as pd
import json
import time # Vamos precisar disso para a RQ2

def load_data(json_path='pr_info_final.json'):
    """Carrega e achata os dados do JSON para análise."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Erro: Arquivo '{json_path}' não encontrado.")
        return None
    except json.JSONDecodeError:
        print(f"Erro: Falha ao decodificar o JSON em '{json_path}'.")
        return None

    # --- Análise de Pull Requests (Code Smells) ---
    # 'record_path' aponta para a lista aninhada que queremos achatar
    # 'meta' especifica quais campos do nível superior queremos copiar para cada linha
    df_prs = pd.json_normalize(
        data,
        record_path=['pull_requests'],
        meta=['owner', 'repo', 'programming_language'] 
    )
    
    # --- Análise de Repositórios (Vulnerabilidades) ---
    # Para CVEs, não precisamos achatar os PRs
    df_repos = pd.json_normalize(data)
    # Removemos a coluna de PRs para uma visualização limpa
    if 'pull_requests' in df_repos.columns:
        df_repos = df_repos.drop(columns=['pull_requests'])
        
    return df_prs, df_repos

def analyze_rq1_code_smells(df_prs, gabarito_path='gabarito_prs.csv'):
    """Calcula métricas de detecção de Code Smells (RQ1)."""
    print("\n--- Análise RQ1 (Code Smells) ---")
    
    # 1. Processar dados do LLM
    # verificando se a lista 'code_smells' está vazia ou não
    df_prs['llm_smell_count'] = df_prs['code_smells'].apply(len)
    df_prs['llm_detected_smell'] = df_prs['llm_smell_count'] > 0
    
    # 2. Carregar gabarito
    try:
        df_gabarito = pd.read_csv(gabarito_path)
    except FileNotFoundError:
        print(f"Erro: Arquivo de gabarito '{gabarito_path}' não encontrado.")
        print("Crie-o manualmente com 'owner,repo,pr_number,real_smell_count'")
        return None
        
    # 3. Juntar LLM vs Gabarito
    df_merged = pd.merge(
        df_prs, 
        df_gabarito, 
        on=['owner', 'repo', 'pr_number']
    )
    
    df_merged['real_has_smell'] = df_merged['real_smell_count'] > 0
    
    # 4. Calcular Métricas de Classificação (Precision, Recall)
    tp = ( (df_merged['llm_detected_smell'] == True) & (df_merged['real_has_smell'] == True) ).sum()
    fp = ( (df_merged['llm_detected_smell'] == True) & (df_merged['real_has_smell'] == False) ).sum()
    fn = ( (df_merged['llm_detected_smell'] == False) & (df_merged['real_has_smell'] == True) ).sum()
    tn = ( (df_merged['llm_detected_smell'] == False) & (df_merged['real_has_smell'] == False) ).sum()
    
    # Taxa de Detecção (Recall)
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    # Precisão
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    print(f"Total de PRs analisados (com gabarito): {len(df_merged)}")
    print(f"Verdadeiros Positivos (TP): {tp}")
    print(f"Falsos Positivos (FP):    {fp}")
    print(f"Falsos Negativos (FN):    {fn}")
    print(f"Taxa de Detecção (Recall) para Code Smells: {recall:.2%}")
    print(f"Precisão para Code Smells: {precision:.2%}")
    
    return df_merged # Retorna para usar na RQ5

def analyze_rq1_cves(df_repos, gabarito_path='gabarito_repos.csv'):
    """Calcula métricas de detecção de CVEs (RQ1)."""
    print("\n--- Análise RQ1 (CVEs) ---")
    # (Lógica similar ao 'analyze_rq1_code_smells', mas a nível de repositório)
    
    # 1. Processar dados do LLM (do 'processor.py' que fizemos)
    df_repos['llm_cve_count'] = df_repos['vulnerability_report'].apply(len)
    df_repos['llm_detected_cve'] = df_repos['llm_cve_count'] > 0
    
    # 2. Carregar gabarito (CSV separado para repos)
    try:
        df_gabarito = pd.read_csv(gabarito_path)
    except FileNotFoundError:
        print(f"Erro: Arquivo de gabarito '{gabarito_path}' não encontrado.")
        print("Crie-o manualmente com 'owner,repo,real_cve_count'")
        return
        
    # 3. Juntar LLM vs Gabarito
    df_merged = pd.merge(df_repos, df_gabarito, on=['owner', 'repo'])
    df_merged['real_has_cve'] = df_merged['real_cve_count'] > 0
    
    # 4. Métricas
    tp = ( (df_merged['llm_detected_cve'] == True) & (df_merged['real_has_cve'] == True) ).sum()
    fn = ( (df_merged['llm_detected_cve'] == False) & (df_merged['real_has_cve'] == True) ).sum()
    
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    print(f"Total de Repos analisados (com gabarito): {len(df_merged)}")
    print(f"Taxa de Detecção (Recall) para CVEs: {recall:.2%}")


def analyze_rq2_tempo(df_prs):
    """Analisa o tempo de processamento (RQ2)."""
    print("\n--- Análise RQ2 (Tempo de Processamento) ---")
    
    # ATENÇÃO: Seus dados NÃO possuem essa informação ainda.
    # Você precisa modificar o 'processor.py'
    
    if 'processing_time_sec' not in df_prs.columns:
        print("Aviso: Coluna 'processing_time_sec' não encontrada.")
        print("Modifique seu 'processor.py' para medir o tempo das chamadas à API Gemini.")
        print("Ex: \n  start_time = time.time()\n  summary = gemini.get_summary_from_diff(diff_content)\n  end_time = time.time()\n  pr_data['processing_time_sec'] = end_time - start_time")
        return
        
    avg_time = df_prs['processing_time_sec'].mean()
    max_time = df_prs['processing_time_sec'].max()
    min_time = df_prs['processing_time_sec'].min()
    
    print(f"Tempo médio de análise por PR (LLM): {avg_time:.2f} segundos")
    print(f"Tempo máximo: {max_time:.2f}s | Tempo mínimo: {min_time:.2f}s")

def analyze_rq5_linguagens(df_merged_prs):
    """Compara a eficácia entre diferentes linguagens (RQ5)."""
    print("\n--- Análise RQ5 (Comparativo por Linguagem) ---")
    
    if df_merged_prs is None:
        print("Análise da RQ5 pulada (depende da RQ1).")
        return
        
    # 'programming_language' veio do 'meta' do json_normalize 
    # Vamos calcular a precisão por linha
    df_merged_prs['acertou_smell'] = (
        (df_merged_prs['llm_detected_smell'] == True) & (df_merged_prs['real_has_smell'] == True) |
        (df_merged_prs['llm_detected_smell'] == False) & (df_merged_prs['real_has_smell'] == False)
    )
    
    # Agrupa por linguagem e calcula a média de acertos
    taxa_acerto_por_linguagem = df_merged_prs.groupby('programming_language')['acertou_smell'].mean()
    
    print("Taxa de Acerto (Acurácia) de Code Smells por Linguagem:")
    print(taxa_acerto_por_linguagem.apply("{:.2%}".format))

def analyze_rq3_rq4_qualitativas(survey_path='survey_respostas.csv'):
    """Analisa dados de surveys (RQ3 e RQ4)."""
    print("\n--- Análise RQ3 & RQ4 (Qualitativa / Survey) ---")
    
    # Estas RQs vêm de surveys, não do 'pr_info_final.json'
    try:
        df_survey = pd.read_csv(survey_path)
    except FileNotFoundError:
        print(f"Aviso: Arquivo de survey '{survey_path}' não encontrado.")
        print("Esta análise depende de um CSV com as respostas dos desenvolvedores.")
        return

    # RQ3: Percepção de utilidade e confiabilidade
    if 'nota_utilidade' in df_survey.columns:
        print(f"Média da 'Nota de Utilidade' (RQ3): {df_survey['nota_utilidade'].mean():.2f} / 5")
    
    if 'confia_na_sugestao' in df_survey.columns:
        print("Distribuição 'Confia na Sugestão?' (RQ3):")
        print(df_survey['confia_na_sugestao'].value_counts(normalize=True).apply("{:.1%}".format))

    # RQ4: Integração não intrusiva
    if 'prefere_comentario_pr' in df_survey.columns:
        print("Preferência de Integração (RQ4):")
        print(df_survey['prefere_comentario_pr'].value_counts(normalize=True).apply("{:.1%}".format))

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    df_prs, df_repos = load_data()
    
    if df_prs is not None and df_repos is not None:
        # RQ1 e RQ5
        df_merged_prs = analyze_rq1_code_smells(df_prs)
        analyze_rq1_cves(df_repos)
        analyze_rq5_linguagens(df_merged_prs)
        
        # RQ2
        analyze_rq2_tempo(df_prs)
        
        # RQ3 e RQ4 (dependem de um arquivo de survey externo)
        analyze_rq3_rq4_qualitativas()