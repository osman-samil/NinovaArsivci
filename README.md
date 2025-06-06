# Ninova Arşivci v4.0

Ninova Arşivci, [Ninova](https://ninova.itu.edu.tr/)'daki ders materyallerini (dosyalar, duyurular, ödevler) topluca bilgisayarınıza indirmek için yazılmış bir Python programıdır.  
(Ninova: İstanbul Teknik Üniversitesinin e-öğrenim merkezi)

## v4.0 Yeni Özellikler
*   **Duyuru Arşivleme**: Artık her dersin duyuruları, `Duyurular` klasörü altında ayrı metin dosyaları (`.txt`) olarak kaydedilir. Dosya adları tarihe göre sıralanmıştır.
*   **Ödev Arşivleme**: Artık derslere ait ödevler `Ödevler` klasörüne indiriliyor. Her ödev için ayrı bir klasör oluşturulur ve bu klasörün içinde ödevin açıklaması, tarihleri, kaynak dosyaları ve **sizin teslim ettiğiniz dosyalar** bulunur.
*   **Daha Sağlam İndirme İşlemi**: Ağ bağlantısında anlık sorunlar yaşandığında indirme işlemi artık pes etmiyor. Başarısız olan indirmeler birkaç kez otomatik olarak yeniden denenir.
*   **Gelişmiş Dosya Adı Desteği**: Türkçe karakterler ve özel semboller içeren dosya adları artık çok daha düzgün bir şekilde indirilip kaydediliyor. Bu, `dosya bulunamadı` hatalarını ve bozuk dosya adlarını önler.
*   **Geliştirilmiş Hata Ayıklama**: Programın ana klasöründe otomatik olarak bir `debug_output` klasörü oluşturulur. Eğer program bir duyuru veya ödev sayfasını ayrıştırırken hata alırsa, sayfanın HTML kodunu bu klasöre kaydederek sorunun teşhisini kolaylaştırır.
*   **Artırılmış Stabilite**: Çoklu iş parçacığı (multi-threading) kullanılırken veritabanı işlemlerinin daha kararlı çalışması için altyapı iyileştirildi.

## Diğer Özellikler
*   İndirilecek dersleri seçme imkanı.
*   Veritabanı desteği sayesinde daha önce indirilmiş dosyaların tekrar indirilmemesi.
*   Son seçilen indirme klasörünü hatırlama.
*   Hatalı şifre girildiğinde programın kapanmak yerine tekrar sorması.

## Kurulum
Bu program [Python yorumlayıcısı (interpreter)](https://www.python.org/downloads/) gerektirir.
1.  Üst sağ köşedeki yeşil "Code" butonuna tıklayın ve zip olarak indirin.
2.  İndirdiğiniz zip dosyasını bir klasöre çıkarın.
3.  Çıkarttığınız klasöre girin ve aşağıdaki komutu çalıştırın. Bu komut gerekli kütüphaneleri yükleyecektir.
```bash
pip install -r requirements.txt
```

## Kullanım
1.  Daha önceden zipten çıkartmış olduğunuz klasöre girin.
2.  Bu klasörde bir uçbirim (terminal) başlatın (Örn: Klasörde boş bir yere Sağ tık > Terminalde Aç).
3.  Aşağıdaki komut ile programı başlatın:
```bash
python main.py
```
Program ilk çalıştığında sizden kullanıcı adı, şifre ve dosyaların indirileceği klasörü seçmenizi isteyecektir. Ardından dersleri listeleyip hangilerini indirmek istediğinizi soracaktır.

### Komut Satırı Parametreleri
Kullanımı ve otomasyonu kolaylaştırmak için komut satırı parametreleri mevcuttur. Komutlar bir arada kullanılabilir ve sıralamaları önemli değildir.

1.  **-u (username)**  
    Kullanıcı adı ve şifrenizi komut satırı üzerinden verir. Program çalışırken bu bilgileri sormaz.
    `python main.py -u kullaniciadim sifrem`

2.  **-d (directory)**  
    Dosyaların indirileceği klasörü belirtir. Program çalışırken klasör seçme penceresi açılmaz.
    `python main.py -d "C:\Users\Bee\Desktop\Ninova"`

3.  **-f (force)**  
    Veritabanını yok sayarak tüm dosyaları en baştan indirir. Silinmiş dosyaları geri getirmek veya arşivi tamamen yenilemek için kullanışlıdır.
    `python main.py -f`
    
4.  **-debug** ve **-verbose**  
    Programın çalışması hakkında detaylı bilgi verir. `-verbose` hangi işlemin ne kadar sürdüğünü, `-debug` ise daha teknik detayları gösterir ve hata ayıklama için HTML dosyaları kaydedebilir.
    `python main.py -verbose`

Tüm komutların bir arada kullanımına örnek:
```bash
python main.py -u kullaniciadim sifrem -d "D:\Dersler\Ninova" -f -debug
```

## Sıkça Sorulan Sorular
1.  **"HATA! src klasörü bulunamadı..." hatası alıyorum.**  
    Programı arşivden çıkarırken `src` klasörünü de çıkardığınızdan emin olun. `main.py` dosyası `src` klasörü içindeki dosyalarla birlikte çalışır.

2.  **"No such file or directory" hatası alıyorum.**  
    Terminali açtığınız klasörün, `main.py` dosyasının bulunduğu klasör ile aynı olduğundan emin olun.

3.  **Şifrem güvende mi?**  
    Evet. Şifreniz sadece Ninova'ya giriş yapmak için kullanılır, hiçbir yere kaydedilmez veya gönderilmez. Kodlar herkese açıktır, kendiniz de inceleyebilirsiniz.

4.  **"-d" komutu ile bir yol belirtmeme rağmen klasör seçme penceresi neden açılıyor?**  
    Belirttiğiniz yolun geçerli ve erişilebilir olduğundan emin olun. Eğer yol bulunamazsa veya geçersizse, program güvenlik amacıyla tekrar sorar.

5.  **Klasörler oluşturuluyor ama bazı dosyalar inmiyor.**  
    Program, daha önce başarıyla indirdiği dosyaları veritabanına kaydeder ve tekrar indirmez. Eğer bir dosyayı sildiyseniz ve tekrar indirmek istiyorsanız, tüm arşivi yenilemek için programı `-f` (force) parametresi ile çalıştırın: `python main.py -f`. Bu, tüm dosyaların yeniden kontrol edilerek indirilmesini sağlar.

## Notlar
*   Eğer indirme klasöründe indirilen dosya ile aynı isimde fakat farklı içerikte bir dosya varsa, yeni indirilen dosyanın sonuna `_yeni` eklenerek kaydedilir.
*   İndirdiğiniz dosyaları silseniz bile, veritabanı kaydı silinmediği sürece tekrar indirilmezler. Tüm arşivi yenilemek için `-f` komutunu kullanın.
*   Programın tamamlanma süresi internet hızınıza ve ders sayınıza göre birkaç dakika sürebilir.

## Hata Bildirimi
Programın GitHub sayfasındaki "Issues" sekmesi altından, aldığınız hataları veya önerilerinizi yazabilirsiniz.