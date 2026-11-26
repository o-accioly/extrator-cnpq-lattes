import os
import glob
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm


def corrigir_mojibake_html(caminho_arquivo):
    """Lê o arquivo de forma segura, corrige o encoding e salva como UTF-8 puro."""
    try:
        # Lê o arquivo em modo binário (lê os bytes crus, sem tentar adivinhar letras)
        with open(caminho_arquivo, 'rb') as f:
            raw_data = f.read()

        # 1. Tenta decodificar como UTF-8 primeiro
        try:
            conteudo = raw_data.decode('utf-8')
            era_utf8 = True
        except UnicodeDecodeError:
            # 2. Se falhar, é porque o arquivo está em Latin-1/ISO-8859-1 no disco
            conteudo = raw_data.decode('latin-1')
            era_utf8 = False

        # Verifica se o texto tem a "assinatura" visual do mojibake (ex: Ã§, Ã£)
        tem_mojibake = 'Ã' in conteudo or 'Â' in conteudo

        # Se não tem o erro visual E já estava no formato UTF-8, podemos pular
        if not tem_mojibake and era_utf8:
            return (True, "Já estava limpo e em UTF-8")

        # Se tem o erro visual, aplicamos a correção (round-trip)
        if tem_mojibake:
            try:
                # Transforma a bagunça de volta em bytes e lê como UTF-8
                conteudo = conteudo.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                # Se a conversão falhar por estar muito corrompido, mantemos o texto como lido
                pass

        # Sobrescreve o arquivo, agora sim, forçando o padrão UTF-8 limpo
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            f.write(conteudo)

        return (True, "Corrigido e convertido para UTF-8 com sucesso")

    except Exception as e:
        return (False, f"Erro inesperado em {caminho_arquivo}: {e}")


def main():
    # Aponte para a sua pasta principal de extração
    pasta_htmls = 'htmls'
    arquivos = glob.glob(os.path.join(pasta_htmls, '**', '*.html'), recursive=True)

    if not arquivos:
        print(f"Nenhum arquivo HTML encontrado em '{pasta_htmls}'.")
        return

    print(f"Iniciando a limpeza de {len(arquivos)} arquivos HTML...\n")

    sucessos = 0
    erros = []

    # Usando o máximo da sua CPU para reescrever os arquivos voando
    num_cpus = os.cpu_count() or 1

    with ProcessPoolExecutor(max_workers=num_cpus) as executor:
        futures = {executor.submit(corrigir_mojibake_html, arq): arq for arq in arquivos}

        with tqdm(total=len(arquivos), desc="Corrigindo arquivos", unit="arq") as pbar:
            for future in as_completed(futures):
                sucesso, mensagem = future.result()
                if sucesso:
                    sucessos += 1
                else:
                    erros.append(mensagem)
                pbar.update(1)

    print("\n" + "=" * 40)
    print("RESUMO DA LIMPEZA")
    print("=" * 40)
    print(f"Total processado: {len(arquivos)}")
    print(f"Corrigidos/Limpos: {sucessos}")
    print(f"Erros encontrados: {len(erros)}")

    if erros:
        print("\nLista de erros:")
        for erro in erros[:10]:  # Mostra só os 10 primeiros para não poluir
            print(f"- {erro}")
        if len(erros) > 10:
            print(f"... e mais {len(erros) - 10} erros.")


if __name__ == "__main__":
    main()