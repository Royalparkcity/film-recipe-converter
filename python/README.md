# 명령줄 변환기

```
pip install pillow numpy
python3 recipefilter.py list --group Leica
python3 recipefilter.py apply 사진폴더/*.jpg -r leica-classic -o 결과/ --strength 0.8
python3 recipefilter.py sheet 사진.jpg -o 비교.jpg --group Kodak
python3 recipefilter.py lut -r all -o luts/        # .cube 3D LUT (Lightroom, VN 등)
```
레시피는 `../app/recipes.json`을 읽는다. Recipe Lab 원본이 바뀌면
`python3 extract_recipes.py <Recipes.java> ../app/recipes.json`으로 다시 뽑는다.
