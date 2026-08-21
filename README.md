# Futures Number

2026 KBO 퓨처스리그 북부·남부리그의 순위, 팀별 예상 최종 경기 수, 1~5위 자력 확정 수를 한 화면에 보여주는 정적 프로토타입입니다.

## 실행

별도 설치 없이 `index.html`을 열거나 로컬 서버를 실행합니다.

```sh
python3 -m http.server 8000
```

## 컨테이너 실행

앱은 컨테이너 내부와 호스트 모두 `54321` 포트를 사용합니다.

```sh
docker compose up -d --build
```

접속 주소는 `http://localhost:54321`입니다. 운영 서버에서는 호스트의 모든 인터페이스에 `54321` 포트를 공개하므로 방화벽과 공유기 포트포워딩 대상을 이 포트로 제한합니다. 도메인과 HTTPS를 사용할 경우에는 Nginx 또는 Caddy 리버스 프록시 구성을 권장합니다.

`data.js`는 로컬 직접 실행과 최초 구동을 위한 기본 데이터입니다. 컨테이너는 최초 실행 시 이 파일을 `runtime/data.js`에 복사하고, 브라우저에서는 런타임 데이터가 기본 데이터를 덮어씁니다. 이후 수집기는 런타임 파일만 갱신하며, 디렉터리가 컨테이너에 마운트되어 있으므로 이미지를 다시 빌드하거나 컨테이너를 재시작할 필요가 없습니다.

```sh
python3 tools/update_kbo_data.py
```

최신 데이터는 다음 명령으로 갱신합니다.

```sh
python3 tools/update_kbo_data.py
```

수집기는 KBO 퓨처스 북부·남부 순위와 현재 월 이후의 일정을 읽어 `runtime/data.js`를 생성합니다. 오늘 이전 경기와 취소 경기는 잔여 경기에서 제외합니다. 기존 데이터와 내용이 같으면 파일을 교체하지 않으며, 변경 시에는 완성된 임시 파일을 원자적으로 교체합니다. 브라우저의 CORS 및 ASP.NET 폼 제약을 피하기 위해 서버 측에서 실행합니다.

다른 출력 경로가 필요하면 `KBO_DATA_PATH` 환경 변수를 지정합니다.

```sh
KBO_DATA_PATH=/path/to/data.js python3 tools/update_kbo_data.py
```

## 서버 자동 갱신

`deploy/systemd`의 서비스와 타이머는 프로젝트가 `/home/rionic/futures-magicnumber`에 배포된 것을 기준으로 합니다. 서버에서 두 파일을 `/etc/systemd/system/`에 설치하고 타이머를 활성화하면 매일 한국 시간 08:00, 16:00, 23:00에 수집기를 실행합니다.

```sh
sudo cp deploy/systemd/futures-number-update.service /etc/systemd/system/
sudo cp deploy/systemd/futures-number-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now futures-number-update.timer
```

실행 결과는 다음 명령으로 확인합니다.

```sh
systemctl list-timers futures-number-update.timer
journalctl -u futures-number-update.service
```

## 계산 원칙

- 승률: `승 / (승 + 패)`, 무승부 제외
- 예상 최종 경기 수: 현재 경기 수 + 아직 취소되지 않은 잔여 일정
- 경쟁팀 전승 가정 필요승: 선두 팀의 시즌 종료 승률이 해당 경쟁팀의 가능한 최고 승률보다 커지는 최소 추가 승수
- 순위별 자력 확정: 경쟁 팀들이 가능한 최고 승률을 기록해도 해당 순위 이내에 드는 최소 추가 승수

팀별 최종 경기 수가 다르므로 일반적인 동일 경기 수 리그의 단순 매직넘버 공식은 사용하지 않습니다.
