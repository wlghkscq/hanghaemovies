from pymongo import MongoClient
import jwt
import datetime
import hashlib
import requests
from flask import Flask, render_template, jsonify, request, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config['UPLOAD_FOLDER'] = "./static/profile_pics"

SECRET_KEY = 'SPARTA'

client = MongoClient('mongodb://test:test@localhost', 27017)
db = client.dbsparta_plus

# 홈화면 API
@app.route('/')
def home():
    # 쿠키 토큰을 받는다
    token_receive = request.cookies.get('mytoken')
    # db에서 hangmovies 정보를 모든 가져온다 id값 상관없이
    movies = list(db.hangmovies.find({}, {'_id': False}))
    try:
        # 로그인된 jwt 토큰을 디코드하여 payload 설정
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        # 로그인 정보를 토대로 user_info 설정
        user_info = db.users.find_one({"username": payload["id"]})

        # 위 설정들이 완료되면  (movies 영화 목록 데이터 , user_info 유저정보 데이터 ) 를 main.html로 렌더링(전달)
        return render_template('main.html', movies=movies, user_info=user_info)

        # jwt 토큰 시간이 만료되서 에러가 뜨면
    except jwt.ExpiredSignatureError:
        #  login 페이지로 이동
        return redirect(url_for("login", msg="로그인 시간이 만료되었습니다."))

        # 유효화에 실패하여 토큰을 디코딩할 수없을 때
    except jwt.exceptions.DecodeError:
        # login 페이지로 이동 msg 보냄
        return redirect(url_for("login", msg="로그인 정보가 존재하지 않습니다."))

# 로그인 화면 이동
@app.route('/login')
def login():
    # msgf를 request를 통해 받는다
    msg = request.args.get("msg")

    # hlogin.htm로 msg와 함께 전달
    return render_template('hlogin.html', msg=msg)


# 영화 상세 페이지 API
@app.route('/detail/<name>')
def detail(name): # name 파라미터 받기
    # 쿠키 토큰을 받는다
    token_receive = request.cookies.get('mytoken')
    # db.hangmovies(영화목록)에서 name에 맞는 값 찾기
    movies = db.hangmovies.find_one({'name': name}, {'_id': False})
    # db.posts(리뷰목록)에서 namedp 맞는 값들 불러오기
    reviews = list(db.posts.find({'title': name}, {'_id': False}))
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])
        user_info = db.users.find_one({"username": payload["id"]})
        return render_template('detail.html', movies=movies, reviews=reviews, user_info=user_info)
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))

# 리뷰 포스팅 API
@app.route('/posting', methods=['POST'])
def posting(): # 영화포스팅
    token_receive = request.cookies.get('mytoken')
    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=['HS256'])

        user_info = db.users.find_one({'username' : payload['id']})

        # detail.html에서 comment 값을 request를 통해 받는다
        comment_receive = request.form['comment_give']
        date_receive = request.form['date_give']
        title_receive = request.form['title_give']

        # doc에 받은 정보를 담는다
        doc = {
            "username" : user_info['username'],
            "comment" : comment_receive,
            "date" : date_receive,
            "title" : title_receive
        }

        # db 리뷰목록에 doc 정보를 넣어준다
        db.posts.insert_one(doc)

        return jsonify({"result": "success", 'msg' : '등록 완료!'})
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return redirect(url_for("home"))


# 로그인 API
@app.route('/sign_in', methods=['POST'])
def sign_in():
    # 로그인
    # 로그인 페이지에서 보낸 username와 password 를 request로 받는다
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']

    # password를 hash함수로 암호화한다
    pw_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()

    # 웨이서 받은 username과 암호화한 password를 db 유저정보에서 조회해서 찾은 다은 result에 담는다
    result = db.users.find_one({'username': username_receive, 'password': pw_hash})

    # result 빈값이 아닐 떄
    if result is not None:

        # payload 변수에 id와 로그인 지속 시간을 담는다.
        payload = {
         'id': username_receive,
         'exp': datetime.utcnow() + timedelta(seconds=60*60)  # 로그인 24시간 유지
        }
        # ( )의 정보를 암호화하여 token에 저장
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256').decode('utf-8')

        # json으로 변환해서 전달
        return jsonify({'result': 'success', 'token': token})
    # 찾지 못하면
    else:
        return jsonify({'result': 'fail', 'msg': '아이디/비밀번호가 일치하지 않습니다.'})


# 회원가입 API
@app.route('/sign_up/save', methods=['POST'])
def sign_up():
    # 회원가입
    # 로그인 페이지에서 보낸 username, passwordm email 정보를 request를 통해 받는다
    username_receive = request.form['username_give']
    password_receive = request.form['password_give']
    email_receive = request.form['email_give']
    password_hash = hashlib.sha256(password_receive.encode('utf-8')).hexdigest()
    # DB에 저장
    doc = {
        "username": username_receive,  # 아이디
        "password": password_hash,  # 비밀번호
        "email": email_receive,
        "profile_name": username_receive,  # 프로필 이름 기본값은 아이디
    }
    db.users.insert_one(doc)
    return jsonify({'result': 'success'})

# 중복확인 API
@app.route('/sign_up/check_dup', methods=['POST'])
def check_dup(): # 아이디 중복확인
    username_receive = request.form['username_give']
    # 받은 USERNAME 정보를 DB에서 찾아서 없으면 False 있으면 True 값을 반환에 exists에 담는다
    exists = bool(db.users.find_one({"username": username_receive}))
    return jsonify({'result': 'success', 'exists': exists})


if __name__ == '__main__':
    app.run('0.0.0.0', port=5000, debug=True)