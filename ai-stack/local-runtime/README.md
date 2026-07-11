# ai-stack/local-runtime/

## Ne yapacak

`hardware-probe/`'un belirlediği tier'a uygun bir yerel LLM'i cihaz üzerinde
çalıştırır. Referans alınan araçlar: [llama.cpp](https://github.com/ggml-org/llama.cpp)
ve/veya [Ollama](https://ollama.com). Amaç, internet bağlantısı olmadan da
temel asistan işlevlerinin (soru-cevap, basit araç çağrısı) çalışabilmesi.

`router/` bu modülü, isteğin yerel olarak karşılanabileceğine karar
verdiğinde çağırır.

## Kapsam dışı (Faz 1)

- Model dosyası indirme YAPILMAYACAK (proje kısıtı: 200 MB üstü indirme yok,
  onaysız başlatılmaz). Model boyutları genelde birkaç GB olduğundan bu
  modülün gerçek implementasyonu ayrı bir onay/altyapı gerektirecek.
- llama.cpp/Ollama kurulumu yapılmayacak.

## Durum

Faz 1 — placeholder. Kod yok. Faz 2'de önce mimari (hangi runtime, model
formatı, quantization stratejisi) netleştirilecek, sonra indirme adımı için
ayrıca onay istenecek.
