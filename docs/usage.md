# Usar o Instante

Instale o `Instante-Setup-<versão>.exe` nas [versões oficiais](https://github.com/redlab-coder/instante/releases/latest). A instalação é por usuário, com atalho no menu Iniciar. A interface abre no navegador padrão e o aplicativo permanece na bandeja do Windows. Não precisa instalar Python, criar conta ou enviar fotografias para um serviço externo.

## Preparar as fotos

1. Adicione arquivos pelo botão ou arraste-os para a área indicada.
2. Confira a orientação em **Em pé**. A análise local por rostos pode sugerir giros; todas as fotos começam a conferir. Paisagens, desenhos e colagens podem não ter sugestão ou apresentar sugestão incorreta.
3. Use **Girar** para 90° no sentido horário ou **180°** para inverter. Marque **Conferida** pelo botão ou pela tecla **F** depois de revisar. No filtro **a conferir**, confirmar seleciona a próxima pendente, retornando ao início se necessário. Fora do filtro, F apenas alterna o estado da foto atual. Qualquer alteração visual pede nova conferência; o giro permanece na foto atual para você avaliar o resultado.
4. **Inteira** mantém a proporção e o conteúdo, preenchendo de branco as sobras. **Preencher** permite recortar, arrastar e ampliar pelo controle Recorte. O número ao lado de cada ajuste permite inserir um valor exato. Centralizar altera só a posição; Restaurar foto retorna os ajustes e a orientação iniciais desta sessão e pede nova conferência.
5. **Impressão** mostra o arquivo horizontal: topo da foto à esquerda e faixa vermelha à direita. Trocar a visualização não muda o arquivo final.

As setas ↑/↓ na lista selecionam fotos. Os botões pequenos na linha alteram sua ordem. Na prévia, arraste para posicionar ou use as setas; Shift aumenta o passo. Margens brancas que já existem no arquivo são preservadas.

O atalho F não atua durante a digitação, com janelas abertas ou enquanto a foto selecionada ainda não apareceu. Segurar a tecla não confirma várias fotos em sequência. Ao concluir o filtro, a lista informa que todas foram conferidas e mantém a última foto visível; F permite marcá-la novamente como a conferir.

Os ajustes afetam o conteúdo da foto. O preenchimento branco do encaixe e as faixas brancas externas detectadas no arquivo permanecem brancos, inclusive durante a prévia rápida e na exportação. Detalhes brancos dentro do conteúdo fotografado continuam recebendo os ajustes normalmente.

O ícone de **Remover todas as fotos**, ao lado de Adicionar na coluna Fotos, limpa a sessão depois de confirmar. Salve o lote primeiro se precisar manter seus ajustes. Os arquivos originais e lotes já salvos são preservados.

## Conferir e exportar

**Conferir lote** abre uma grade em pé. Selecione uma montagem para ajustar. As montagens abaixo do editor mostram a orientação de impressão; clique para ampliar e baixar individualmente.

**Exportar** mostra o progresso e gera um JPG, ou um ZIP com JPGs individuais para várias fotos. Os nomes mantêm referência ao original e recebem sufixos quando necessário para evitar colisões. A exportação usa os ajustes no momento do clique e os originais completos. Uma falha identifica o arquivo afetado; o aplicativo não entrega silenciosamente um ZIP parcial.

Fotos com detalhe insuficiente recebem um aviso de ampliação. Isso não impede exportar: o arquivo final registra 300 DPI, mas a ampliação não cria o detalhe ausente no original.

## Salvar e retomar

O botão **Salvar lote**, no cabeçalho, baixa um `.instante` com cópias integrais das fotos, ordem, ajustes e estados de conferência. Guarde esse arquivo para continuar após encerrar. **Abrir lote** restaura seu conteúdo, mesmo que os originais tenham mudado de pasta. Abrir um lote substitui a sessão atual; salve-a primeiro se precisar preservá-la. O lote contém suas fotografias e pode ocupar aproximadamente o tamanho dos originais somados.

Durante a execução, recarregar a aba no mesmo navegador/perfil recupera a sessão. Uma aba edita por vez em navegadores com Web Locks; **Usar nesta aba** transfere a edição. Essa recuperação temporária não substitui salvar o lote.

## Instalação e atualizações

A versão aparece ao lado de Instante. Na versão instalada, novas versões publicadas são baixadas e verificadas em segundo plano; a instalação acontece ao encerrar normalmente, sem interromper a edição. O ícone da bandeja permite reabrir, verificar atualizações ou encerrar. Sem internet, a edição continua disponível. A edição portátil `Instante-Portable.exe` funciona sem instalação e não aplica atualizações automáticas.

## Limites

JPG, PNG, WebP, BMP e TIFF (primeira página), até 50 MB e 60 megapixels por foto, 100 fotos e 4 GB de originais por lote. Transparência é composta sobre branco; EXIF é interpretado e perfis ICC válidos são convertidos para sRGB. É necessário espaço temporário para originais, lotes abertos e exportações. Os downloads seguem a pasta e as permissões configuradas no navegador.

Imprima a **100% / tamanho real**. Confirme as medidas e o corte com uma amostra antes de produzir um pedido inteiro.

[← Documentação](README.md)
