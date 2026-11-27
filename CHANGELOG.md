# Changelog

Todas as mudanças relevantes do Extrator CNPq Lattes. Gerado pelo towncrier a partir de `changelog.d/` em cada release (não editar à mão).

<!-- towncrier release notes start -->

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


