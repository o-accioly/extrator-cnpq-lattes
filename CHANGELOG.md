# Changelog

Todas as mudanças relevantes do Extrator CNPq Lattes. Gerado pelo towncrier a partir de `changelog.d/` em cada release (não editar à mão).

<!-- towncrier release notes start -->

## [2.1.1] — 2026-11-27
### Correções

- Quando o site do CNPq devolve a lista de resultados com erro do servidor, o programa tenta de novo em vez de marcar o nome como não encontrado; se o erro continuar, o nome fica como falha e é refeito ao continuar a extração.

## [2.1.0] — 2026-11-27
### Funcionalidades

- O Windows ganha um instalador (`ExtratorLattes-<versão>-setup.exe`): um arquivo só, que instala sem pedir administrador, cria atalho no Menu Iniciar (e, se quiser, na Área de Trabalho) e tem desinstalador. O `.zip` continua disponível.
- O programa verifica o ambiente ao abrir (Chrome, pasta de trabalho, acesso ao CNPq e as próprias bibliotecas), mostra o que falta e não deixa começar uma extração que não ia funcionar.

### Melhorias

- No Windows, a coleta não abre mais uma janela preta de console junto com o Chrome, e o perfil do Chrome fica fora da pasta de trabalho para não ir para o OneDrive.

### Correções

- O programa abre mesmo quando a pasta de trabalho sumiu ou as configurações salvas estão corrompidas, voltando aos valores padrão e avisando.
- A busca por nomes e a coleta voltam a funcionar no executável do Windows, que saía sem uma parte da automação do Chrome.
- No executável, o desempate de homônimos volta a usar a comparação de nomes rápida e precisa, em vez da simplificada.

## [2.0.1] — 2026-11-27
### Documentação

- O repositório agora tem licença MIT e instruções para baixar o programa pronto.

## [2.0.0] - 27/11/2026

### Novidades

- **coleta:** Coleta pela busca do CNPq com os mesmos filtros do site, retomável
- **nomes:** Busca por planilha de nomes com desempate de homônimos e template
- **interface:** Interface gráfica com abertura animada, assistentes e acompanhamento da extração
- **base:** Base de currículos pesquisável e perfil com o currículo original igual ao site

### Correções

- Corrige artigos perdidos, total de produção e retomada do coletor
- Corrige codificação, colunas duplicadas e palavras-chave no extrator

### Desempenho

- **parser:** Reescreve a extração com lxml numa passada só, 8x mais rápida

### Documentação

- README e capturas de tela

### CI e build

- Executável com PyInstaller, Qt podado e scripts de build
- Testes, .exe, changelog e release automáticos; runner próprio

### Testes

- Testes do núcleo, da base e do visualizador

### Manutenção

- Importa cnpq_lattes do zip


