# Desenvolvimento

Python, Pillow e interface local em HTML, CSS e JavaScript, seguindo a organização do Moldura. A aplicação escuta em `127.0.0.1`, valida Host, Origin e token da sessão e não publica as fotos na rede. YuNet/OpenCV fornece sugestões locais de orientação por rostos; o modelo acompanha o programa, sem download durante a operação.

## Executar

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

A distribuição oficial usa Python 3.14 e Windows de 64 bits. Para testes de navegador, instale `playwright==1.59.0` e tenha o Microsoft Edge disponível.

| Caminho | Responsabilidade |
|---|---|
| `app.py` | Serviço local, importação, tarefas de exportação e APIs |
| `engine.py` | Geometria, orientação aplicada, encaixe e cores |
| `orientation.py` | Sugestões por rostos e marcos faciais |
| `projects.py` | Lotes portáteis com originais e ajustes validados |
| `photo_store.py` | Originais temporários, prévias e cache limitado |
| `desktop.py`, `updater.py`, `version.py` | Windows, distribuição e versão |
| `ui/` | Interface e ícones |
| `assets/` | Ícone, marcador da instalação e modelo local |
| `scripts/`, `installer/`, `.github/` | Compilação, instalador e publicação |
| `tests/` | Processamento, projetos, API, navegador e instalação |

## Verificar

```powershell
python -m unittest discover -s tests -v
python app.py --isolated --no-browser --no-tray --no-updates --port 18758
# Em outro terminal:
python tests/browser_check.py http://127.0.0.1:18758
python tests/refinement_browser_check.py http://127.0.0.1:18758
```

O teste de navegador verifica edição, preservação das regras de encaixe, lotes salvos, exportação, recuperação, transferência entre abas, falha de prévia, teclado e layouts de 320 a 1440 pixels. Gera capturas com ilustrações próprias, sem fotografias pessoais.

O teste de refinamento cobre a fila de conferência, F durante digitação e em janelas, repetição da tecla, a última foto, prévia atrasada, aba sem edição e preservação do branco na prévia rápida, definitiva e no JPG. Também exercita cancelar, falhar e repetir a remoção de todas as fotos e reabrir o lote salvo. Os dois testes de navegador rodam no executável na validação de distribuição.

```powershell
python tests/batch_check.py URL PASTA_DE_REFERENCIA
python tests/heavy_photo_check.py URL
```

Use uma instância isolada para essa verificação: ela importa o lote indicado e substitui a sessão ao testar salvar/abrir. Não grava fotografias nos artefatos ou no repositório. Verifica a quantidade exportada, dimensões, DPI, perfil ICC, faixa vermelha e hashes dos originais. Essa verificação técnica não aprova a orientação visual de cada foto.

`heavy_photo_check.py` importa 12 imagens sintéticas de 30 megapixels, exercita o arraste e verifica a exportação. Use outra instância isolada, pois o teste adiciona fotos à sessão.

## Compilar

```powershell
python -m pip install -r requirements-build.txt playwright==1.59.0
./scripts/bootstrap_inno.ps1
python scripts/build_windows.py
python tests/packaged_check.py dist/Instante-Portable.exe
python tests/installer_check.py
```

`dist/` recebe o executável portátil, o instalador, o manifesto de atualização e os checksums. A compilação e os artefatos de teste não entram no Git.

## Memória e arquivos

Os originais são guardados byte a byte em diretórios temporários locais. Fontes de edição têm até 1800 px; o cache decodificado é limitado a 160 MiB. A exportação lê os originais, processando uma foto por vez e retendo suas referências até concluir. Tarefas de exportação usam arquivos temporários e envio em blocos; resultados recentes são limitados a oito e expiram na criação de novas tarefas após uma hora.

O `.instante` é um ZIP com `project.json` e originais numerados, validados por SHA-256. A abertura verifica formato, limites e estrutura; não extrai caminhos fornecidos pelo arquivo. Uma abertura inválida mantém a sessão anterior. O lote só substitui a sessão depois que todas as fotos foram decodificadas.

Faixas inteiramente brancas nas bordas são identificadas na importação por varreduras estreitas, com tolerância de cinco níveis para quase branco. Seus limites normalizados acompanham tanto os originais quanto as fontes leves. Os ajustes são aplicados ao retângulo de conteúdo antes da composição sobre branco; o preenchimento não entra no cálculo de contraste. Detalhes brancos internos à foto continuam editáveis. Não se trata de segmentação de objetos nem de remoção das margens existentes.

Encerramento forçado pode deixar temporários no Windows. Salvar um lote é a forma de manter fotos e ajustes após reiniciar. Instante e Moldura usam mutexes, identificadores e atualizadores distintos.

[← Documentação](README.md)
