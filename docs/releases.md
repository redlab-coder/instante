# Publicar uma versão

1. Atualize `version.py`, `CHANGELOG.md` e `RELEASE_NOTES.md`.
2. Valide processamento, projetos, navegador, executável e instalação.
3. Atualize capturas reais com o conteúdo de demonstração.
4. Envie o código e uma tag `v<versão>` correspondente a `version.py`.

O GitHub Actions executa os testes, compila no Windows, verifica o programa e o instalador e publica os arquivos já testados. Uma alteração na branch principal é verificada, mas somente uma tag de versão publica uma release.

As releases incluem `PolaroidEditor-Setup-<versão>.exe`, `PolaroidEditor-Portable.exe`, `update.json` e `SHA256SUMS.txt`. O atualizador instalado aceita apenas o endereço de instalador esperado neste repositório e verifica tamanho e SHA-256 antes de instalar ao encerrar.

O README deve apontar para um instalador publicado; alinhe seu link à versão de entrega.

[← Documentação](README.md)
