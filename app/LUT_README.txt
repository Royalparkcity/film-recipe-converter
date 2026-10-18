필름 레시피 LUT (.cube, 33포인트) - 77개
=========================================

Recipe Lab 레시피(라이카, 후지, 리코, 코닥, 일포드 ...)를 3D LUT로 옮긴 파일이에요.
필름 레시피 변환기 앱(웹/안드로이드)과 같은 계산으로 만들었어요.

■ 프리미어 프로에서 쓰기
1. 클립을 고르고 Lumetri Color 패널을 열어요.
2. Creative(크리에이티브) > Look(룩) 드롭다운에서 "Browse...(찾아보기)"를 골라요.
3. 이 폴더의 .cube 파일을 선택해요.
4. 바로 아래 Intensity(강도) 슬라이더로 세기를 조절해요. 앱의 "강도"와 같은 역할이에요.
   폰 사진처럼 이미 진한 영상은 70~80%가 자연스러워요.

드롭다운에 항상 보이게 하려면 .cube 파일을 Premiere Pro의 Creative LUT 폴더에 복사하고
프리미어를 다시 켜면 돼요. 폴더 위치는 버전마다 다를 수 있어서, 확실한 방법은 위의 Browse예요.

■ 어떤 영상에 맞나요
- 일반(Rec.709) 영상 기준이에요. 카메라 픽처 프로파일을 끄거나 표준으로 찍은 영상, 폰 영상에 바로 쓰면 돼요.
- S-Log2 / S-Log3 같은 로그 영상은 먼저 Rec.709로 바꾼 다음 적용해야 해요.
  (Lumetri의 Basic Correction > Input LUT에 Sony 공식 변환 LUT를 넣고, 이 파일은 Creative > Look에 넣으세요.)

■ LUT에 담기지 않는 것
LUT는 색만 바꿀 수 있어서 선명도, 거친 흑백(HC Mono)의 입자, Toy 카메라 비네팅은 빠져 있어요.
필요하면 프리미어의 Lumetri Creative > Sharpen, Vignette나 Noise 효과로 더해 주세요.

■ 참고
원래 레시피는 Sony 카메라 설정값(Creative Style, 채도/대비, 화이트밸런스, 노출, DRO 등)이라
다른 회사 색을 그대로 복제한 것이 아니라 비슷하게 흉내 낸 근사치예요.
레시피 데이터: Recipe Lab (github.com/voxivoid/recipe-lab-sony-pmca), MIT 라이선스.
다른 프로그램(다빈치 리졸브, 파이널 컷, 포토샵, 라이트룸 등)에서도 .cube를 지원하면 똑같이 쓸 수 있어요.
