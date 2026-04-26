# Miron 🚀

Miron, macOS için özel olarak geliştirilmiş, ekrandaki herhangi bir bölgeyi seçerek anlık (real-time) çeviri yapmanızı sağlayan yerel ve yapay zeka destekli bir araçtır.

<div align="center">
  <img src="ss/selectiong.png" alt="Miron Seçim Alanı" width="800">
</div>

Oyun oynarken, video izlerken veya yabancı dildeki bir belgeyi okurken; Miron'un seçim çerçevesini hedefin üzerine sürükleyin, çift tıklayın ve anında Türkçe çevirisini görün. Arka planda **Apple Vision Framework** ile kusursuz metin tanıma (OCR) yapar ve **Ollama** kullanarak tamamen çevrimdışı, gizlilik odaklı bir çeviri sunar.

<div align="center">
  <img src="ss/running.png" alt="Miron Aktif Çeviri" width="800">
</div>

## ✨ Özellikler

*   **Native macOS OCR (Apple Vision):** Apple'ın kendi donanım hızlandırmalı Vision Framework'ü sayesinde çok hızlı ve hatasız metin okuma.
*   **Ollama ile Yerel Çeviri:** Verileriniz asla internete gitmez. Ollama üzerinden yerel olarak çalışan `translategemma` modeli ile bağlama uygun, doğal Türkçe çeviri.
*   **Akıllı UI (Glassmorphism):** Seçtiğiniz alanın üzerini karartarak orijinal metni hafifçe gizler ve yerine sinematik bir altyazı gibi Türkçe çeviriyi yerleştirir.
*   **Geri Bildirim Döngüsü Koruması:** Miron, kendi çizdiği çeviri metnini OCR aşamasında görmezden gelerek sonsuz döngüleri (feedback loop) engeller.
*   **Asenkron ve Performanslı:** PySide6 (Qt) ve `asyncio` kullanılarak tasarlandı. Çeviri arka planda yapılırken arayüz asla donmaz.

## 🛠 Kurulum

### Gereksinimler
*   **macOS:** Uygulama, Quartz ve Apple Vision Framework kullandığı için sadece macOS üzerinde çalışır.
*   **Python 3.9+**
*   **Ollama:** Bilgisayarınızda [Ollama](https://ollama.com) kurulu ve çalışır durumda olmalıdır.

### Adımlar

1.  **Ollama Modeli İndirme:**
    Terminali açıp uygulamanın çeviri için kullandığı modeli indirin:
    ```bash
    ollama run translategemma
    ```

2.  **Bağımlılıkları Yükleme:**
    Projeyi bilgisayarınıza klonladıktan sonra, bir sanal ortam oluşturun ve gereksinimleri yükleyin:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Ekran Kaydı İzni:**
    Uygulamanın ekranı okuyabilmesi için **Sistem Ayarları > Gizlilik ve Güvenlik > Ekran Kaydı** bölümünden Terminal'e (veya IDE'nize) izin vermeniz gerekmektedir.

## 🚀 Kullanım

Projeyi başlatmak için sağlanan shell betiğini çalıştırabilirsiniz:

```bash
./run.sh
```

**Nasıl Kullanılır?**
1. Ekranda beliren mor çerçeveyi, çevirmek istediğiniz metnin (örneğin bir oyun altyazısı) üzerine sürükleyip boyutlandırın.
2. Çerçevenin içine **çift tıklayın**.
3. Sol üstte minik bir "⟳ Taranıyor..." ve ardından "◉ Çevriliyor..." yazısı belirecek.
4. Çeviri tamamlandığında arka plan hafifçe kararır ve Türkçe metin çerçevenin tam ortasına yansıtılır!
5. Taramayı durdurmak için çerçeveye tekrar çift tıklayabilirsiniz.

## ⚙️ Yapılandırma (`config.py`)

Uygulamanın çalışma mantığını `miron/config.py` üzerinden özelleştirebilirsiniz:
*   `ollama_model`: Kullanılacak LLM modeli (Varsayılan: `translategemma`).
*   `ocr_interval_ms`: Ekranın kaç milisaniyede bir taranacağı (Varsayılan: `2000`).
*   `system_prompt`: Yapay zekaya giden, çevirinin nasıl yapılacağını belirten direktif.

## 📝 Sorun Giderme (Loglama)
Uygulama çalışırken terminal kirliliğini önlemek ve tarama döngüsüne girmemek için tüm kayıtlar `miron.log` dosyasına yazılır. Eğer çeviriler gelmiyorsa veya bir sorun yaşıyorsanız bu dosyayı inceleyebilirsiniz.
