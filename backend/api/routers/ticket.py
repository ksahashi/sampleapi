from typing import Optional
from fastapi import APIRouter, Depends
from schemas.ticket import Seat
from schemas.ticket import (
    Facility,
    Ticket,
    TicketListResponse,
    TicketDetailResponse,
    TicketPurchase,
)
from cruds.ticket_list_after import get_ticket_list_after
from cruds.ticket_detail import get_ticket_detail
from cruds.ticket import (
    fetch_movie_ticket_by_user_id,
    fetch_movie_ticket_detail,
    fetch_theater_schedule,
    update_ticket_refund,
    update_share_ticket_ticketing_notification,
    distribute_tc_ticket,
    distribute_ticket_manually,
)
from database import get_db, get_reader_db
from schemas.ticketing_information_notification import (
    TicketingInformationNotificationRequest,
    TicketingRefundRequest,
)
from cruds.ticket import update_ticket_notification_issue
from realtime.user import verify_tokens_and_user_id
from error import NotFound, InternalServerError
from utils.movie import subtitles_dubbing_name
from realtime.purchase import post_ticket_purchase
from common.router import CustomRouter
from models.movie import Movie
from models.theater_schedule import TheaterSchedule
from schemas.concession import Concession
from cruds.concession import fetch_concession

router = APIRouter(route_class=CustomRouter)


@router.get(
    "/before/{user_id}",
    response_model=TicketListResponse,
    summary="鑑賞前モバイルチケット一覧",
    description="指定したユーザーの鑑賞前モバイルチケットの一覧を取得する",
)
async def read_ticket_list_before(
    user_id: str = Depends(verify_tokens_and_user_id),
    db=Depends(get_reader_db),
):
    movie_tickets = fetch_movie_ticket_by_user_id(db=db, user_id=user_id, before=True)

    ticket_list = list()
    for mt in movie_tickets:
        movie = db.query(Movie).filter(
            Movie.movie_code == mt.movie_code,
            Movie.is_deleted.is_(False)
        ).first()
        theater_schedule = fetch_theater_schedule(db=db, movie_code=mt.movie_code)
        _title = _get_title_from_movie_or_schedule(movie=movie, theater_schedule=theater_schedule)
        _title_ja = _get_title_ja_from_movie_or_schedule(movie=movie, theater_schedule=theater_schedule)
        _thumbnail_url = _get_thumbnail_url_from_movie(movie=movie)

        if not _title or not _title_ja:
            raise InternalServerError("タイトルを取得できませんでした")

        concessions_list = fetch_concession(db=db, theater_code=mt.theater_code)

        mobile_order = {}
        concessions = list()
        for cs in concessions_list:
            concession_info = Concession(
                concession_id = cs.concession_id
                , concession_name = cs.concession_name
                , mobile_order_url = cs.mobile_order_url
                ,caution_text = cs.caution_text
            )
            concessions.append(concession_info)

        if concessions:
            mobile_order.update(concession = concessions)

        res = Ticket(
            transaction_id=mt.transaction_id,
            management_movie_code=mt.management_movie_code,
            movie_code=mt.movie_code,
            title=_title,
            title_ja=_title_ja,
            showing_date=str(mt.jyouei_day),
            showing_start_time=mt.jyouei_start_time,
            showing_end_time=mt.jyouei_end_time,
            theater_code=mt.theater_code,
            theater_name=mt.theater.theater_name,
            purchase_number=mt.kounyu_cd,
            thumbnail_url=_thumbnail_url,
            exists_movie_data=True if movie else False,
            mobile_order=mobile_order,
        )
        ticket_list.append(res)
    return {"ticket_list": ticket_list}


@router.get(
    "/after/{user_id}",
    response_model=TicketListResponse,
    summary="鑑賞後モバイルチケット一覧",
    description="指定したユーザーの鑑賞後モバイルチケットの一覧を取得する",
)
async def read_ticket_list_after(
    user_id: str = Depends(verify_tokens_and_user_id),
    db=Depends(get_reader_db),
):
    movie_tickets = fetch_movie_ticket_by_user_id(db=db, user_id=user_id, before=False)

    ticket_list = list()
    for mt in movie_tickets:
        theater_schedule = mt.theater.theater_schedule
        _title = _get_title_from_movie_or_schedule(movie=mt.movie, theater_schedule=theater_schedule)
        _title_ja = _get_title_ja_from_movie_or_schedule(movie=mt.movie, theater_schedule=theater_schedule)
        _thumbnail_url = _get_thumbnail_url_from_movie(movie=mt.movie)

        mobile_order = {}

        if not _title or not _title_ja:
            print('タイトルを取得できませんでした,movie_code: {mt.movie.movie_code}')
            # エラーが発生しても処理を続行する
            continue

        res = Ticket(
            transaction_id=mt.transaction_id,
            management_movie_code=mt.management_movie_code,
            movie_code=mt.movie_code,
            title=_title,
            title_ja=_title_ja,
            showing_date=str(mt.jyouei_day),
            showing_start_time=mt.jyouei_start_time,
            showing_end_time=mt.jyouei_end_time,
            theater_code=mt.theater_code,
            theater_name=mt.theater.theater_name,
            purchase_number=mt.kounyu_cd,
            thumbnail_url=_thumbnail_url,
            exists_movie_data=True if mt.movie else False,
            mobile_order = mobile_order,
        )
        ticket_list.append(res)
    return {"ticket_list": ticket_list}


@router.get(
    "/{user_id}/{transaction_id}",
    response_model=TicketDetailResponse,
    summary="モバイルチケット詳細",
    description="指定したモバイルチケットの詳細情報を取得する",
)
async def read_ticket_detail(
    transaction_id: str,
    user_id: str = Depends(verify_tokens_and_user_id),
    db=Depends(get_reader_db),
):
    movie_ticket = fetch_movie_ticket_detail(db=db, user_id=user_id, transaction_id=transaction_id)
    if movie_ticket is None:
        raise NotFound()
    movie = db.query(Movie).filter(
        Movie.movie_code == movie_ticket.movie_code,
        Movie.is_deleted.is_(False)
    ).first()
    theater_schedule = fetch_theater_schedule(db=db, movie_code=movie_ticket.movie_code)

    _subtitles_dubbing_code = None
    _subtitles_dubbing_name = None
    # subtitles_dubbing_codeは作品が紐づいたスケジュールのみで取得可能
    if theater_schedule:
        _subtitles_dubbing_code = theater_schedule.subtitles_dubbing_code
        if _subtitles_dubbing_code:
            _subtitles_dubbing_name = subtitles_dubbing_name(_subtitles_dubbing_code)

    _title = _get_title_from_movie_or_schedule(movie=movie, theater_schedule=theater_schedule)
    _title_ja = _get_title_ja_from_movie_or_schedule(movie=movie, theater_schedule=theater_schedule)
    _thumbnail_url = _get_thumbnail_url_from_movie(movie=movie)

    if not _title or not _title_ja:
        raise InternalServerError("タイトルを取得できませんでした")

    # 座席情報を シート番号の昇順にソート
    seats_sorted = sorted(movie_ticket.seats, key=(lambda x: x.seat_no))

    # 暫定対応：取得したfacilityが「SCREEN X PREMIUM THEATER」だった場合、「SCREEN X」に置き換え
    if movie_ticket.facility_code == "SCREEN X PREMIUM THEATER":
        movie_ticket.facility_code = "SCREEN X"
        movie_ticket.facility_name = "SCREEN X"

    respons_data = TicketDetailResponse(
        transaction_id=movie_ticket.transaction_id,
        # 詳細にない場合はnullで返したほうがいいかも
        management_movie_code=movie_ticket.management_movie_code,
        movie_code=movie_ticket.movie_code,
        title=_title,
        title_ja=_title_ja,
        showing_date=str(movie_ticket.jyouei_day),
        showing_start_time=movie_ticket.jyouei_start_time,
        showing_end_time=movie_ticket.jyouei_end_time,
        theater_code=movie_ticket.theater_code,
        theater_name=movie_ticket.theater.theater_name,
        purchase_number=movie_ticket.kounyu_cd,
        thumbnail_url=_thumbnail_url,
        facility_list=[
            Facility(
                facility_code=movie_ticket.facility_code, facility_name=movie_ticket.facility_name
            )
        ]
        if movie_ticket.facility_code and movie_ticket.facility_name
        else [],
        subtitles_dubbing_code=_subtitles_dubbing_code,
        subtitles_dubbing_name=_subtitles_dubbing_name,
        screen_name_ja=movie_ticket.screen_name,
        screen_name_en=None,
        seat_list=[
            Seat(
                seat_number=seat.seat_no,
                kensyu_name=seat.kensyu_nm,
                waribiki_onaori_name=seat.waribiki_onaori_name,
                kaiin_no=seat.kaiin_no
            )
            for seat in seats_sorted
        ],
        phone_number=movie_ticket.phone_number,
        purchase_qr_code=movie_ticket.purchase_qr_code,
        exists_movie_data=True if movie else False,
    )
    return respons_data


@router.post(
    "/notification/issue",
    summary="発券情報通知",
    description="デジタルチケットの発券情報とトランザクションIDをアプリサーバに送信し、購入情報のステータスを「ご利用済み」に変更する",
)
async def ticket_notification_issue(
    data: TicketingInformationNotificationRequest, db=Depends(get_db)
):
    update_ticket_notification_issue(db=db, data=data)

    for ticket in data.list:
        update_share_ticket_ticketing_notification(
            db=db, ticket=ticket
        )

    return {"message": "success"}


@router.post("/purchase", summary="購入情報", description="トランザクションIDからチケット購入ページへの遷移URLを取得する")
async def ticket_purchase(data: TicketPurchase):
    res = post_ticket_purchase(
        data.transaction_id, data.access_token_cinemileage, data.invitation_param
    )
    res.encoding = "shift_jis"

    return res.text


@router.post(
    "/refund",
    summary="払い戻し情報通知",
    description="TCアプリ購入情報データをもとに、デジタルチケットの払戻情報とトランザクションIDをアプリサーバへ送信し、購入情報のステータスを「払戻済み」に変更する",
)
async def ticket_refund(data: TicketingRefundRequest, db=Depends(get_db)):
    print("Request:", data)
    # ダミーデータ返却のためupdate_ticket_refundメソッドはコメントアウト
    update_ticket_refund(db=db, data=data)
    return {"message": "success"}


@router.post(
    "/distribution",
    summary="TCチケット配布",
    description="TCチケットを配布するテストAPI",
)
async def distribute_tc_ticket_route(ticket_type: str, user_id: str, db=Depends(get_db)):
    distribute_tc_ticket(ticket_type=ticket_type, user_id=user_id, db=db)
    return {"message": "success"}


def _get_title_from_movie_or_schedule(movie: Optional[Movie], theater_schedule: Optional[TheaterSchedule]) -> Optional[str]:
    title = None
    if movie:
        title = movie.title
    return title


def _get_title_ja_from_movie_or_schedule(movie: Optional[Movie], theater_schedule: Optional[TheaterSchedule]) -> Optional[str]:
    title_ja = None
    if movie:
        title_ja = movie.title_ja
    return title_ja


def _get_thumbnail_url_from_movie(movie: Optional[Movie]) -> str:
    thumbnail_url = ""
    if movie:
        thumbnail_url = movie.thumbnail_url or ""
    return thumbnail_url


"""
TCチケットを配布するためのAPI
クエリパラメータは以下の通り
receipt_number: 受付番号
email_address: ユーザーのメールアドレス
"""


@router.get(
    "/distribution",
    summary="TCチケット配布",
    description="TCチケットを配布するテストAPI",
)
async def distribute_tc_ticket_manually(
    receipt_number: str, email_address: str, db=Depends(get_db)
):
    result = distribute_ticket_manually(
        receipt_number=receipt_number,
        email_address=email_address,
        db=db,
    )
    if result == "1":
        return {"message": "success"}
    else:
        return {"message": "error"}
