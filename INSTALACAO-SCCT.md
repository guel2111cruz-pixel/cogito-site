# COGITO // entrega V2 Beta e app SCCT

Base: repositório público `guel2111cruz-pixel/cogito-site`, snapshot `da47288` baixado em 03/10/2026. Nenhuma alteração foi enviada ao GitHub ou publicada automaticamente.

## O que foi preparado

- `index.html`: preserva o visual original; cartão de projetos revisado, menu com app SCCT.
- `projetos.html`: página já existente com A.M. e VR preservada; diferencia descrição de funcionalidade de validação do código.
- `diario.html`: LOG_015 Nmap e LOG_016 Wireshark já existiam. Mantidos sem duplicação, com nota sobre verificação documental e ausência dos arquivos de evidência; link Projetos corrigido.
- `feira/`: PWA independente, escuro/verde, quatro escolhas fictícias, interface offline e escolha persistente no tablet.
- `control/`: ponte HTTPS local, controle USB autenticado, registro de solicitações e firmware de referência.

AI Thinker ESP32-CAM é o modelo informado. Não há `.ino` no repositório. O firmware original não foi inspecionado. O sketch fornecido **não inicializa câmera nem streaming**; gravá-lo substitui o programa atual. Para preservar a câmera, guarde o código original e adapte o controle depois de revisar seu uso de Wi-Fi e UART. Não há API HTTP presumida da ESP32.

## Redes e funcionamento

```text
Tablet -- Wi-Fi da equipe --> notebook/PLOT (HTTPS + ponte)
                                    |
                              USB / UART autenticado
                                    |
                             AI Thinker ESP32-CAM
                                    |
                        AP COGITO-DEMO para a demonstração
```

Use um roteador da equipe, com senha forte, para notebook e tablet. Internet não é necessária durante a feira. O tablet NÃO deve ficar conectado ao AP cuja senha muda. Ao reiniciar o AP da placa, seus clientes caem e precisam reconectar com a nova senha; USB e rede da equipe continuam independentes. Desative o isolamento de clientes nesse roteador e reserve o IP do notebook.

O operador autoriza a sessão antes de entregar o tablet. A escolha dispara o envio automaticamente nessa sessão. O app oculta os botões após o toque e só informa sucesso após `APPLIED` da placa. Sem conexão, mantém uma única escolha pendente. Ao voltar, o operador toca em aplicar/verificar: não há reprodução automática de rodadas antigas. Não depende de Background Sync.

O notebook registra a solicitação antes do envio serial. Repetir o mesmo identificador consulta o resultado ou reenvia a mesma escolha; a placa reconhece a última solicitação persistida. Outra rodada é bloqueada enquanto há resultado incerto. Uma resposta já confirmada representa a aplicação naquela rodada, não uma leitura contínua do estado atual da placa.

## Publicar as páginas no GitHub Pages

1. Faça backup/branch do repositório. Substitua os três HTML completos e adicione `feira/`. Preserve os demais arquivos e `midia/`.
2. Faça commit e push pelo seu GitHub Desktop/editor. Em Settings → Pages, mantenha a origem de publicação usada no projeto, normalmente `main` e raiz.
3. Confira home, menu, página Projetos, diário, quiz e layout no celular/tablet.
4. A PWA no Pages permite demonstrar a interface offline, mas **não controla a placa**: o Pages não executa a ponte Python. Para controle real, instale o app a partir da ponte HTTPS local descrita abaixo. São origens diferentes e têm instalações/armazenamentos diferentes.

Não publique certificados, chaves preenchidas, arquivos `.sqlite3`, arquivos `.env` ou o firmware com segredo. A ponte serve apenas os arquivos de `feira/`, mesmo se executada dentro deste pacote.

## Preparar a AI Thinker ESP32-CAM

1. Antes de gravar, obtenha o `.ino` atual e preserve suas configurações. O sketch entregue serve para ensaio do AP e do controle, não substitui uma câmera funcional de forma transparente.
2. No Arduino IDE, instale o pacote oficial `esp32` da Espressif e selecione **AI Thinker ESP32-CAM**. Abra `control/firmware/scct_control/scct_control.ino`.
3. Gere duas chaves distintas, uma para tablet/ponte e outra para USB/placa. No PowerShell:

```powershell
python -c "import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(32))"
```

4. Guarde a primeira como `SCCT_TOKEN`. Copie a segunda no `CONTROL_KEY` do sketch e guarde como `SCCT_DEVICE_KEY`. Não use uma senha fraca do demo como chave de controle.
5. Use o adaptador/programador apropriado à sua placa. Em uma placa sem USB integrado, use USB–UART com **níveis lógicos de 3,3 V**, GND comum, TX→U0R e RX→U0T. Confira o esquema da sua revisão antes de ligar. A alimentação da placa e os níveis UART são coisas distintas; nunca aplique sinal lógico de 5 V na UART. Providencie alimentação estável adequada à placa.
6. Para upload via UART, coloque GPIO0 em GND, reinicie e grave. Após upload, remova GPIO0 de GND e reinicie para executar. Não deixe o jumper de boot conectado durante a feira.
7. Feche o Monitor Serial antes de iniciar a ponte: ela precisa da porta a 115200 baud. O AP inicial é `COGITO-DEMO`, senha `12345678`. Todas as quatro opções têm pelo menos 8 caracteres.

O controle USB não fica exposto pelo AP fraco. O token USB autentica comandos no enlace físico; não é criptografia nem proteção contra alguém com acesso físico aos fios/programador. Não exponha a ponte à Internet. Só uma ponte e um operador devem controlar a placa durante as rodadas.

## HTTPS local e instalação no tablet

Service worker e instalação offline precisam de contexto seguro. `http://IP-do-notebook` não basta no tablet; ignorar um aviso de certificado também não é um procedimento confiável de instalação. O certificado deve ser confiável no navegador do tablet e conter o IP/nome usado.

1. No notebook, instale Python e execute, na pasta do projeto:

```powershell
python -m pip install -r control/requirements.txt
```

2. Prepare uma autoridade local e um certificado para o IP reservado, por exemplo com `mkcert` instalado previamente. Exemplo para IP **192.168.1.20** (substitua pelo IP real):

```powershell
mkcert -install
mkcert -cert-file scct-cert.pem -key-file scct-key.pem 192.168.1.20 localhost 127.0.0.1
mkcert -CAROOT
```

3. Transfira somente `rootCA.pem` da pasta indicada ao tablet e instale-o como certificado de autoridade confiável. **Não transfira `rootCA-key.pem`**. Android: configurações de segurança/criptografia → instalar certificado CA (nomes variam). iPad: instale o perfil e habilite confiança total para a CA nas configurações de certificados. Dispositivos gerenciados podem bloquear isso. Abra o endereço HTTPS e confirme que não há aviso de certificado; se houver, pare a instalação e corrija nome/IP/confiança. Após a feira, remova a CA do tablet se ela não for mais necessária.
4. No PowerShell, configure os dois segredos e inicie a ponte (substitua porta, IP e caminhos):

```powershell
$env:SCCT_TOKEN = 'COLE_A_PRIMEIRA_CHAVE_DE_64_HEX'
$env:SCCT_DEVICE_KEY = 'COLE_A_SEGUNDA_CHAVE_DE_64_HEX'
python control/bridge.py --port COM5 --cert scct-cert.pem --key scct-key.pem --origin https://192.168.1.20:8443 --db scct-jobs.sqlite3
```

5. Se o firewall bloquear, permita a porta 8443 somente na rede privada da equipe. Use `/dev/ttyUSB0` em vez de COM5 se o PLOT estiver no Linux. A ponte também funciona no Linux com os mesmos argumentos, definindo as variáveis de ambiente no shell utilizado.
6. No tablet conectado à rede da equipe, abra `https://192.168.1.20:8443/feira/`. Aguarde “Interface preparada para uso offline”. No Chrome/Android, menu → Instalar app/Adicionar à tela inicial. No Safari/iPad, Compartilhar → Adicionar à Tela de Início. A opção de instalação depende do navegador e do sistema.
7. Abra o app instalado, desconecte o Wi-Fi e reabra: a interface deve continuar disponível. Reconecte, abra Área da equipe e autorize com `SCCT_TOKEN`. Feche essa área e entregue o tablet. Escolhas locais são fictícias, sem dados pessoais; a ocultação é visual, não um cofre contra inspeção técnica.

As chaves ficam na sessão/memória do app e variáveis do processo; não entram no cache ou URLs. A escolha/identificador permanecem no armazenamento local até preparar a próxima rodada ou descartar. Evite fechar o app se ele avisar que o armazenamento está indisponível. Se perder o tablet/limpar seu armazenamento enquanto há resultado incerto, o banco da ponte preserva o identificador. Faça recuperação supervisionada antes de outra rodada; não apague o banco para ignorar o bloqueio.

## Ensaio obrigatório antes da SCCT

- Autorize e escolha cada uma das quatro opções. Confirme a resposta no app e conecte um segundo dispositivo ao AP usando a senha escolhida. A resposta do firmware confirma a chamada de configuração, não substitui esse teste externo de associação.
- Verifique que os clientes do AP caem na troca e que o tablet permanece na rede da equipe.
- Corte o Wi-Fi do tablet antes do toque: deve ocultar/guardar a escolha sem anunciar sucesso. Reconecte e aplique/verifique a mesma rodada.
- Interrompa USB durante o envio: o app deve mostrar estado incerto, nunca sucesso inventado. Restabeleça USB e verifique a mesma solicitação; a ponte deve impedir uma rodada diferente enquanto ela está incerta.
- Reabra app/ponte/placa: teste recuperação da escolha local, banco e registro persistido da placa. Não deixe outro programa alterar o AP durante os testes.
- Código errado: controle recusado. Sem código: a interface pode registrar uma escolha local, mas não alterar a placa. Confirme que arquivos de controle e banco não são acessíveis pela ponte.
- Finalizada a rodada, Área da equipe → Preparar próximo participante. Descartar escolha local não desfaz mudança na placa. Encerrar sessão remove a autorização da memória.

## Verificação realizada e limites

Verificação de sintaxe JS/Python e testes automatizados da ponte com serial simulada: validação, autenticação HTTP, rejeição de outra origem, proteção de arquivos, repetição sem nova aplicação, persistência e bloqueio de estado incerto. Esses testes **não são teste de hardware**.

Execute novamente:

```powershell
node --check feira/app.js
node --check feira/sw.js
python -m unittest discover -s control -p test_bridge.py -v
```

Não foram validados na placa: compilação Arduino, upload, câmera, alimentação, associação Wi-Fi, comportamento real da UART e instalação em tablet físico. O código original da câmera é necessário para integração final com streaming. O pacote é uma implementação de referência revisável, com essa validação pendente.

## Referências

- Espressif, Wi-Fi AP, `softAP` e desconexão: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html
- MDN, service worker/contexto seguro: https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope
- MDN, HTTPS e mixed content: https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Mixed_content
- Nmap, descoberta sem scan de portas: https://nmap.org/book/man-host-discovery.html
- Nmap, portas padrão: https://nmap.org/book/man-port-specification.html
- Wireshark, campo `ip.addr`: https://www.wireshark.org/docs/dfref/i/ip.html

Os LOG_015/016 têm conteúdo técnico conferido nessas fontes; anexar saídas/capturas reais continua necessário para verificar os resultados experimentais.
