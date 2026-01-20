# Steps to run this code on my Windows machine rather than my laptop:

1. `git clone https://github.com/cissna/course-evaluation-predictor.git`
2. `cd course-evaluation-predictor`
3. create a new file `.env`
   1. containing `SIS_API_KEY="[redacted]"`
4. make sure python version is `Python 3.13.7`
   1. if it's not what do i do 💀
5. `python -m venv venv`
6. `.\venv\Scripts\activate`
7. `pip install -r requirements.txt`
8. `python scrape_catalog_by_term.py`

```powershell
git clone https://github.com/cissna/course-evaluation-predictor.git
cd course-evaluation-predictor
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
