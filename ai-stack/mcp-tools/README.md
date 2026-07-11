# ai-stack/mcp-tools/

## Ne yapacak

Navigator asistanının sistemle etkileşim kurmasını sağlayan araç katmanı.
[Model Context Protocol (MCP)](https://modelcontextprotocol.io) standardını
kullanarak, hem yerel hem bulut modellerinin aynı araç setine (dosya
sistemi, uygulama kontrolü, sistem ayarları vb.) erişmesini sağlar.

`router/` hangi model'in (yerel/bulut) isteği karşıladığından bağımsız
olarak, araç çağrıları bu modül üzerinden tek bir arayüzle yürütülür.

## Kapsam dışı (Faz 1)

- Gerçek MCP server implementasyonu yazılmayacak.
- Sistem düzeyinde araç entegrasyonları (dosya erişimi, uygulama kontrolü)
  tasarlanmayacak — sadece bu README ile niyet belgeleniyor.

## Durum

Faz 1 — placeholder. Kod yok.
