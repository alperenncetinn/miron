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

*   **Native macOS OCR (Apple Vision):** Apple'ın kendi donanım hızlandırmalı Vision Framework'ü sayesinde çok hızlı ve hatasız metin okuma. Pikselleri Retina ekran (points) ölçeklerine göre milimetrik hizalar.
*   **Donanım Hızlandırmalı Kaydırma Takibi (Optical Flow):** Oyun oynarken sayfayı veya kamerayı kaydırdığınızda, OCR işlemini beklemeden çeviri kutuları 25 FPS (40ms) hızla anlık olarak metinle birlikte kayar (`VNTranslationalImageRegistrationRequest`).
*   **Ollama ile Yerel veya Google ile Hızlı Çeviri:** İster Ollama üzerinden internete bağlanmadan gizlilik odaklı kaliteli çeviri, isterseniz de tek tıkla **Google Translate** tabanlı deterministik "Hızlı Çeviri" (anlık) moduna geçiş imkanı.
*   **Akıllı UI:** Orijinal metnin tam üzerine, sinematik bir altyazı gibi Türkçe çeviriyi yerleştirir. Arka planı tamamen şeffaf bıraktığı ve fare tıklamalarını yoksaydığı için oyunu oynamaya veya bilgisayarı kullanmaya engelsiz devam edebilirsiniz. Uzun süre yazı bulunmazsa 7 saniye içerisinde ekrandan otomatik kaybolur.
*   **Sistem Çubuğu (System Tray) Kontrolü:** Kapatma, "Oyun Modu"na geçiş veya "Hızlı Çeviri" gibi ayarları sağ üst köşedeki "M" ikonundan saniyeler içinde değiştirebilirsiniz.
*   **Geri Bildirim Döngüsü Koruması:** Miron, kendi çizdiği çeviri metnini OCR aşamasında görmezden gelerek sonsuz döngüleri engeller.

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
1. Ekranda beliren mor çerçeveyi, çevirmek istediğiniz metnin (örneğin bir oyun altyazısı) üzerine sürükleyip boyutlandırın. "F" tuşuna basarak tam ekran yapabilirsiniz.
2. Çerçevenin içine **çift tıklayın** veya sağ üstteki **Menü Çubuğu (System Tray) ikonundan "Taramayı Başlat"** seçeneğine tıklayın.
3. Çeviri modundayken pencere hayalet (click-through) moda geçer, yani pencerenin arkasına, oyununuza rahatça tıklamaya devam edebilirsiniz.
4. Çeviri tamamlandığında arka plan tamamen şeffaf şekilde Türkçe metin orijinalinin tam üzerine yansıtılır!
5. Taramayı durdurmak, **Oyun Modu'nu** (Kaydırma takibi olmadan tam ekran çeviri) veya **Hızlı Çeviri'yi** etkinleştirmek için sağ üst köşedeki **M (Miron) ikonuna** tıklayabilirsiniz. Çıkış işlemini de yine buradan yapmalısınız.

## ⚙️ Yapılandırma (`config.py`)

Uygulamanın çalışma mantığını `miron/config.py` üzerinden özelleştirebilirsiniz:
*   `ollama_model`: Kullanılacak LLM modeli (Varsayılan: `translategemma`).
*   `ocr_interval_ms`: Ekranın kaç milisaniyede bir taranacağı (Varsayılan: `2000`).
*   `system_prompt`: Yapay zekaya giden, çevirinin nasıl yapılacağını belirten direktif.

## 📝 Sorun Giderme (Loglama)
Uygulama çalışırken terminal kirliliğini önlemek ve tarama döngüsüne girmemek için tüm kayıtlar `miron.log` dosyasına yazılır. Eğer çeviriler gelmiyorsa veya bir sorun yaşıyorsanız bu dosyayı inceleyebilirsiniz.
