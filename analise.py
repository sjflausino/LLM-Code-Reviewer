import pandas as pd
import json
import sys
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Configuração de estilo dos gráficos
sns.set_theme(style="whitegrid")

def load_llm_json(file_path):
    """Carrega o JSON gerado pela ferramenta LLM-Code-Reviewer."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Extrai a lista de repositórios
        if isinstance(data, dict) and "repositories" in data:
            repos_data = data["repositories"]
        else:
            print("❌ Formato JSON antigo ou inválido. Esperado chave 'repositories'.")
            return None

        # Normaliza os dados de PRs em um DataFrame Pandas
        df_prs = pd.json_normalize(
            repos_data,
            record_path=['pull_requests'],
            meta=['owner', 'repo', 'programming_language'],
            errors='ignore'
        )
        
        # Se não houver PRs, tenta carregar commits (caso tenha sido rodado em modo commit)
        if df_prs.empty and len(repos_data) > 0 and 'commits_analysis' in repos_data[0]:
            df_prs = pd.json_normalize(
                repos_data,
                record_path=['commits_analysis'],
                meta=['owner', 'repo', 'programming_language'],
                errors='ignore'
            )
           
            # Renomeia para padronizar com a lógica de PRs
            if 'commit_hash' in df_prs.columns:
                df_prs.rename(columns={'commit_hash': 'pr_number'}, inplace=True) 

        return df_prs
    except Exception as e:
        print(f"❌ Erro ao carregar JSON da LLM: {e}")
        return None

def load_ground_truth(file_path):
    """Carrega o CSV de Gabarito Manual (A Verdade Absoluta)."""
    try:
        # Espera colunas: owner, repo, pr_number, tem_smell_real (bool/int) or gabarito_tem_smell
        df = pd.read_csv(file_path)
        # Garante que pr_number seja string para bater com o JSON
        df['pr_number'] = df['pr_number'].astype(str)
        return df
    except Exception as e:
        print(f"⚠️ Gabarito não encontrado ou inválido ({file_path}). A RQ1 será pulada.")
        return None

def calcular_metricas_classificacao(df):
    """Calcula TP, FP, FN, TN, Precisão, Recall e F1."""
    
    # Definições:
    # LLM Diz SIM (True) | Gabarito Diz SIM (True) -> TP
    # LLM Diz SIM (True) | Gabarito Diz NÃO (False) -> FP
    # LLM Diz NÃO (False) | Gabarito Diz SIM (True) -> FN
    # LLM Diz NÃO (False) | Gabarito Diz NÃO (False) -> TN

    tp = len(df[(df['llm_detectou'] == True) & (df['gabarito_tem_smell'] == True)])
    fp = len(df[(df['llm_detectou'] == True) & (df['gabarito_tem_smell'] == False)])
    fn = len(df[(df['llm_detectou'] == False) & (df['gabarito_tem_smell'] == True)])
    tn = len(df[(df['llm_detectou'] == False) & (df['gabarito_tem_smell'] == False)])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0

    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "Precision": precision, "Recall": recall, "F1": f1_score, "Accuracy": accuracy
    }

def gerar_matriz_confusao(metrics, output_dir):
    """Gera e salva o gráfico da Matriz de Confusão."""
    matrix = [[metrics['TN'], metrics['FP']], 
              [metrics['FN'], metrics['TP']]]
    
    try:
        plt.figure(figsize=(6, 5))
        sns.heatmap(matrix, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['Não (Real)', 'Sim (Real)'],
                    yticklabels=['Não (LLM)', 'Sim (LLM)'])
        plt.xlabel('Ground Truth (Gabarito)')
        plt.ylabel('Predição da LLM')
        plt.title('Matriz de Confusão: Detecção de Code Smells')
        
        filename = os.path.join(output_dir, 'matriz_confusao.png')
        plt.savefig(filename)
        print(f"📊 Gráfico salvo: {filename}")
        plt.close()
    except Exception as e:
        print(f"⚠️ Erro ao gerar gráfico de matriz: {e}")

def analisar_tempo(df, output_dir):
    """Gera gráficos de análise de tempo (RQ2)."""
    if 'processing_time_sec' not in df.columns:
        return

    try:
        plt.figure(figsize=(10, 6))
        sns.histplot(df['processing_time_sec'], kde=True, bins=15)
        plt.title('Distribuição do Tempo de Processamento da LLM por PR')
        plt.xlabel('Tempo (segundos)')
        plt.ylabel('Frequência')
        
        filename = os.path.join(output_dir, 'distribuicao_tempo.png')
        plt.savefig(filename)
        print(f"📊 Gráfico salvo: {filename}")
        plt.close()
    except Exception as e:
        print(f"⚠️ Erro ao gerar gráfico de tempo: {e}")
    
    print("\n⏱️  Estatísticas de Tempo (RQ2):")
    print(df['processing_time_sec'].describe().to_string())

def main():
    if len(sys.argv) < 2:
        print("Uso: python analise.py <arquivo_resultado_llm.json> [arquivo_gabarito.csv]")
        sys.exit(1)

    json_file = sys.argv[1]
    gabarito_file = sys.argv[2] if len(sys.argv) > 2 else "gabarito_prs.csv"
    
    # Cria diretório para salvar gráficos
    output_dir = "resultados_analise"
    os.makedirs(output_dir, exist_ok=True)

    print(f"--- 🚀 Iniciando Análise de: {json_file} ---")

    # 1. Carregar Dados da LLM
    df_llm = load_llm_json(json_file)
    if df_llm is None or df_llm.empty:
        print("Erro: DataFrame vazio ou inválido.")
        sys.exit(1)

    # Prepara coluna de detecção da LLM (Assumindo que code_smells é uma lista)
    # Se a lista não for vazia, detectou algo.
    df_llm['llm_detectou'] = df_llm['code_smells'].apply(lambda x: len(x) > 0 if isinstance(x, list) else False)
    df_llm['pr_number'] = df_llm['pr_number'].astype(str)

    # 2. Carregar Gabarito (Ground Truth)
    df_gabarito = load_ground_truth(gabarito_file)

    if df_gabarito is not None:
        # Faz o MERGE dos dados (Cruza LLM com Gabarito pelo ID do PR)
        # Atenção: Certifique-se que as colunas 'owner', 'repo', 'pr_number' existem em ambos
        try:
            df_final = pd.merge(df_llm, df_gabarito, on=['owner', 'repo', 'pr_number'], how='inner')
            print(f"\n📈 PRs com Gabarito Correspondente: {len(df_final)}")
        except KeyError as e:
            print(f"❌ Erro ao cruzar dados: Coluna {e} faltando no CSV ou JSON.")
            sys.exit(1)
        
        if not df_final.empty:
            # --- RQ1: Eficácia ---
            metricas = calcular_metricas_classificacao(df_final)
            print("\n🏆 Resultados RQ1 (Eficácia da LLM):")
            print(f"   Precisão: {metricas['Precision']:.2%}")
            print(f"   Recall:   {metricas['Recall']:.2%}")
            print(f"   F1-Score: {metricas['F1']:.2%}")
            print(f"   Acurácia: {metricas['Accuracy']:.2%}")
            print(f"   (TP={metricas['TP']}, FP={metricas['FP']}, FN={metricas['FN']}, TN={metricas['TN']})")
            
            gerar_matriz_confusao(metricas, output_dir)
            
            # --- RQ3: Comparação por Linguagem (CORRIGIDO) ---
            print("\n🌍 Resultados RQ3 (Por Linguagem):")
            
            # Filtra apenas colunas necessárias para evitar FutureWarning do Pandas 2.2+
            # Usa pd.Series no apply para expandir o dicionário em colunas
            if 'programming_language' in df_final.columns:
                grouped = df_final.groupby('programming_language')[['llm_detectou', 'gabarito_tem_smell']].apply(
                    lambda x: pd.Series(calcular_metricas_classificacao(x))
                )
                
                # O resultado do apply acima retorna um DataFrame onde o índice é a linguagem.
                # Não usamos .items() (que itera colunas), mas sim .iterrows() (que itera linhas).
                results_lang = []
                for lang, row in grouped.iterrows():
                    results_lang.append({
                        "Linguagem": lang,
                        "Precision": row['Precision'],
                        "Recall": row['Recall'],
                        "F1": row['F1']
                    })
                    
                df_lang = pd.DataFrame(results_lang)
                print(df_lang.to_string(index=False, formatters={
                    'Precision': '{:.2%}'.format, 
                    'Recall': '{:.2%}'.format, 
                    'F1': '{:.2%}'.format
                }))
            else:
                print("⚠️ Coluna 'programming_language' não encontrada para análise da RQ3.")

        else:
            print("⚠️ A interseção entre o JSON da LLM e o Gabarito CSV resultou em 0 linhas. Verifique os IDs dos PRs.")
    
    # --- RQ2: Tempo (Independe do gabarito) ---
    analisar_tempo(df_llm, output_dir)

    print(f"\n✅ Análise concluída. Gráficos salvos em: ./{output_dir}")

if __name__ == "__main__":
    main()