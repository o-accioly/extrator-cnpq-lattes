import os
import sys
import time

# Tenta importar as funções dos scripts existentes
try:
    from coletorLattes import iniciar_coleta
except ImportError as e:
    _erro_coletor = e
    def iniciar_coleta():
        print(f"Erro: Não foi possível carregar o coletorLattes.py: {_erro_coletor}")
        print("Instale as dependências com: pip install -r requirements.txt")

try:
    from extratorDadosLattes import main as iniciar_extracao
except ImportError as e:
    _erro_extrator = e
    def iniciar_extracao():
        print(f"Erro: Não foi possível carregar o extratorDadosLattes.py: {_erro_extrator}")
        print("Instale as dependências com: pip install -r requirements.txt")

def limpar_tela():
    if os.name == 'nt':
        os.system('cls')
    else:
        # Tenta limpar a tela apenas se a variável TERM estiver definida
        if os.environ.get('TERM'):
            os.system('clear')
        else:
            # Caso contrário, apenas imprime algumas linhas em branco ou nada
            # para evitar a mensagem de erro "TERM environment variable not set"
            print("\n" * 100)

def apresentacao():
    limpar_tela()
    print("="*60)
    print("      EXTRATOR CURRICULO LATTES - CNPq Lattes      ")
    print("="*60)
    ascii_art = (
        "      ___           ___           ___                       ___           ___       ___      \n"
        "     /\  \         /\  \         /\  \          ___        /\  \         /\__\     |\__\     \n"
        "    /::\  \       /::\  \       /::\  \        /\  \      /::\  \       /:/  /     |:|  |    \n"
        "   /:/\:\  \     /:/\:\  \     /:/\:\  \       \:\  \    /:/\:\  \     /:/  /      |:|  |    \n"
        "  /::\~\:\  \   /:/  \:\  \   /:/  \:\  \      /::\__\  /:/  \:\  \   /:/  /       |:|__|__  \n"
        " /:/\:\ \:\__\ /:/__/ \:\__\ /:/__/ \:\__\  __/:/\/__/ /:/__/ \:\__\ /:/__/        /::::\__\ \n"
        " \/__\:\/:/  / \:\  \  \/__/ \:\  \  \/__/ /\/:/  /    \:\  \ /:/  / \:\  \       /:/~~/~    \n"
        "      \::/  /   \:\  \        \:\  \       \::/__/      \:\  /:/  /   \:\  \     /:/  /      \n"
        "      /:/  /     \:\  \        \:\  \       \:\__\       \:\/:/  /     \:\  \    \/__/       \n"
        "     /:/  /       \:\__\        \:\__\       \/__/        \::/  /       \:\__\               \n"
        "     \/__/         \/__/         \/__/                     \/__/         \/__/               \n"
    )
    print(ascii_art)
    time.sleep(8)

def menu():
    while True:
        limpar_tela()
        print("="*60)
        print("                        MENU PRINCIPAL                        ")
        print("="*60)
        print("\n[1] Iniciar Extrator (Coletar IDs e Currículos)")
        print("[2] Processar arquivos extraídos (Gerar Planilha/Relatórios)")
        print("[0] Sair")
        print("\n" + "="*60)
        
        opcao = input("Escolha uma opção: ").strip()
        
        if opcao == '1':
            print("\nIniciando Coletor...")
            time.sleep(1)
            try:
                # O coletor precisa do webdriver-manager e selenium
                iniciar_coleta()
            except KeyboardInterrupt:
                print("\nColeta interrompida pelo usuário.")
            except Exception as e:
                print(f"\nOcorreu um erro durante a coleta: {e}")
            input("\nPressione Enter para voltar ao menu...")
            
        elif opcao == '2':
            print("\nIniciando Processamento dos arquivos extraídos...")
            # Garante que a saída seja liberada antes de iniciar o processo pesado
            sys.stdout.flush()
            time.sleep(1)
            try:
                # O extratorDadosLattes processa todos os HTMLs na pasta htmls
                iniciar_extracao()
            except KeyboardInterrupt:
                print("\nProcessamento interrompido pelo usuário.")
            except Exception as e:
                print(f"\nOcorreu um erro durante o processamento: {e}")
            
            input("\nPressione Enter para voltar ao menu...")
            
        elif opcao == '0':
            print("\nSaindo... Até logo!")
            time.sleep(1)
            break
        else:
            print("\nOpção inválida. Tente novamente.")
            time.sleep(1)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        apresentacao()
        menu()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
        sys.exit(0)
