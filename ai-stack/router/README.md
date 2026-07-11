# ai-stack/router/

## Ne yapacak

Navigator asistanına gelen her isteği, `hardware-probe/` tier bilgisi,
kullanıcı tercihi (gizlilik/maliyet/hız) ve isteğin karmaşıklığı gibi
sinyallere göre `local-runtime/` veya `cloud-bridge/`'e yönlendiren hibrit
karar katmanı. Asistan panelinin (`shell/`) ve `mcp-tools/`'un birleştiği
merkezi nokta.

## Kapsam dışı (Faz 1)

- Gerçek yönlendirme mantığı/kodu yazılmayacak.
- Herhangi bir model çağrısı yapılmayacak.

## Durum

Faz 1 — placeholder. Kod yok. Faz 2'de önce `hardware-probe/` ve
`local-runtime/` şekillendikten sonra ele alınacak (bu ikisine bağımlı).
