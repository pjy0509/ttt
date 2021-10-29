import numpy as np
import datetime
import xml.etree.ElementTree as ET

from urllib.request import Request
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.parse import quote_plus

from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

import mysql.connector

# Get Total Data in list from Data.go.kr
now_dt = int(datetime.datetime.now().strftime('%H%M%S'))
if now_dt > 4000:
  end_create_dt = int(str(datetime.datetime.now().date()).replace('-',''))
else:
  end_create_dt = int(str(datetime.datetime.now().date()).replace('-','')) - 1

url = 'http://openapi.data.go.kr/openapi/service/rest/Covid19/getCovid19InfStateJson'
queryParams = '?' + urlencode({ quote_plus('ServiceKey') : 'cwrcT5TevRi39dJ3+8FTHHLLQyxGCWKNdMYBYqAwwrCHqPAK/1ZHilEhfJ31syfsZ1BOVUiLL4DIjRLU+Hfg2w==', quote_plus('startCreateDt') : '20200122', quote_plus('endCreateDt') : '%d' % (end_create_dt) })
request = Request(str(url) + queryParams)
request.get_method = lambda: 'GET'
response_body = urlopen(request).read().decode('ascii')

root = ET.fromstring(response_body)
root = root.findall('.//item')

dp_date = []
dp_decide_cnt = []

index = 0
for i in root:
  dp_decide_cnt.append(int(i.findtext(".//decideCnt")))
  dp_date.append(len(root) - index)
  index = index + 1

dp_date.reverse()
dp_decide_cnt.reverse()

dp_decide_cnt_daily = []
t = []

index = 0
for i in root:
  if index + 1 < len(root):
    # Infectious
    dp_decide_cnt_daily.append(float(dp_decide_cnt[index + 1]) - float(dp_decide_cnt[index]))
    if dp_decide_cnt_daily[index] < 0 or dp_decide_cnt_daily[index] > 5000:
      dp_decide_cnt_daily[index] = dp_decide_cnt_daily[index - 1]
    # t
    t.append(dp_date[index])
  index = index + 1

day = 1
max_exponent = 8

# Get Next Daily Infectious
dp_decide_cnt_daily_new_lowest_mse = [0] * day
t_new = [0] * day
mse = [0] * max_exponent
index = 0
for i in range(0, max_exponent):
  poly = PolynomialFeatures(degree = index)
  X = np.array(t).reshape(-1, 1)
  Y = np.array(dp_decide_cnt_daily)
  X_poly = poly.fit_transform(X)
  lin_reg = LinearRegression()
  lin_reg.fit(X_poly, Y)
  lin_reg.intercept_, lin_reg.coef_
  X_new = np.linspace(0, len(t) + day, len(t) + day).reshape(-1, 1)
  X_new_poly = poly.transform(X_new)
  dp_decide_cnt_daily_new = lin_reg.predict(X_new_poly)
  pipeline = Pipeline([("polynomial_features", poly), ("linear_regression", lin_reg)])
  pipeline.fit(X.reshape(-1, 1), Y)
  scores = cross_val_score(pipeline, X.reshape(-1, 1), Y, scoring = "neg_mean_squared_error", cv = 10)
  mse[index] = -scores.mean()
  if index != 0:
    if mse[index] < mse[index - 1]:
      decide_min_mean_squared_error = -scores.mean()
      for i in range(0, day):
        t_new[i] = len(t) + i
        dp_decide_cnt_daily_new_graph = dp_decide_cnt_daily_new
        dp_decide_cnt_daily_new_lowest_mse[i] = round(dp_decide_cnt_daily_new[len(t) + i])
  index = index + 1

dp_decide_cnt_daily_final = dp_decide_cnt_daily + dp_decide_cnt_daily_new_lowest_mse
t_final = t + t_new

mysql_connector = mysql.connector.connect(
    host="localhost",
    user="root",
    passwd="1234",
    database="corona"
  )
mc = mysql_connector.cursor()

for i in range(0, len(t_final)):
  mc.execute("""SELECT * FROM decide WHERE date = %s""", (int(t_final[i]),))
  if len(mc.fetchall()) == 0:
    query = "INSERT INTO decide (date, decide) VALUES (%s, %s)"
    value = (int(t_final[i]), int(dp_decide_cnt_daily_final[i]))
    print(value)
    mc.execute(query, value)
    mysql_connector.commit()
  else:
    query = "UPDATE decide SET decide=%s WHERE date=%s"
    value = (int(dp_decide_cnt_daily_final[i]), int(t_final[i]))
    print(value)
    mc.execute(query, value)
    mysql_connector.commit()