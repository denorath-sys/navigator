# ai-stack/cloud-bridge/

## Ne yapacak

`router/` yerel modelin yetersiz olduğuna veya kullanıcının bulut tercih
ettiğine karar verdiğinde devreye giren köprü. Bulut LLM sağlayıcılarına
(ör. Anthropic Claude API ve benzeri) bağlanır, kimlik bilgilerini/anahtar
yönetimini ve isteğe bağlı gizlilik filtrelemesini (isteğe gönderilmeden
önce hassas veri maskeleme gibi) üstlenir.

`mcp-tools/` üzerinden gelen araç çağrılarının bulut modeller için de aynı
şekilde çalışmasını sağlamak bu modülün sorumluluğundadır.

## Kapsam dışı (Faz 1)

- Gerçek API entegrasyonu yazılmayacak.
- Kimlik bilgisi/anahtar yönetimi tasarlanmayacak.

## Durum

Faz 1 — placeholder. Kod yok.
