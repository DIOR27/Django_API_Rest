from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from dotenv import load_dotenv
from .serializers import UserSerializer
from .models import User

import webbrowser
import requests
import time
import os

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv(
    "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/callback/"
)
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_URL = "https://api.spotify.com/v1/me/top/artists"
SCOPE = "user-top-read"

spotify_tokens = {}


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


def spotify_auth():
    """
    Genera la URL de autenticación para Spotify.

    Retorna un diccionario con la clave "auth_url" que contiene la URL de autenticación.
    """
    auth_url = (
        f"{SPOTIFY_AUTH_URL}?"
        f"response_type=code&client_id={SPOTIFY_CLIENT_ID}"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={SCOPE}"
    )
    return {"auth_url": auth_url}


@api_view(["GET"])
def callback(request):
    """
    Maneja la respuesta de la autenticación de Spotify.

    Este endpoint es llamado por Spotify después de que el usuario concede permiso
    para acceder a su cuenta. El código de autorización se intercambia por un token
    de acceso que se utiliza para hacer solicitudes a la API de Spotify.

    Args:
        request (HttpRequest): Objeto de solicitud HTTP que contiene el código
        de autorización en los parámetros de consulta.

    Returns:
        Response: Una respuesta HTTP que contiene un diccionario con los tokens
        de acceso y refresh y el tiempo de expiración del token de acceso si la
        solicitud es exitosa. Si falla, devuelve un mensaje de error.
    """
    code = request.GET.get("code")

    global spotify_tokens

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()

        spotify_tokens = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data["expires_in"],
        }

        return Response(
            spotify_tokens,
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"error": "Error al obtener el token de acceso."},
            status=status.HTTP_400_BAD_REQUEST,
        )


def get_spotify_token():
    """
    Obtiene el token de acceso de Spotify.

    Si no se ha autenticado previamente, abre la ventana de autenticación
    en el navegador predeterminado. Luego, espera hasta que se obtenga el token
    de acceso y lo devuelve.

    Si no se obtiene el token de acceso en 120 segundos, se lanza una excepción.

    Returns:
        str: El token de acceso de Spotify.
    """
    global spotify_tokens

    if not spotify_tokens:
        auth_url = spotify_auth().get("auth_url")
        webbrowser.open(auth_url)

        timeout = 120
        start_time = time.time()

        while not spotify_tokens:
            if time.time() - start_time > timeout:
                return Response(
                    {
                        "error": "Se agotó el tiempo de espera. No se pudo obtener el token de acceso."
                    },
                    status=status.HTTP_408_REQUEST_TIMEOUT,
                )
            time.sleep(1)

    access_token = spotify_tokens["access_token"]

    return access_token


def get_track_info(access_token: str, track: str, artist: str):
    """
    Obtiene la informaci n de una canci n de Spotify dada su nombre y artista.

    Args:
        access_token (str): El token de acceso del usuario.
        track (str): El nombre de la canci n.
        artist (str): El nombre del artista.

    Returns:
        list: Una lista con la informaci n de la canci n, que contiene los campos
            "track_name", "artist", "album", "release_date" y "album_type".

    Raises:
        Response: Si ocurre un error al obtener la información de la canción.
    """
    url = "https://api.spotify.com/v1/search"

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"q": f"{track} {artist}", "type": "track", "limit": 1}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        search_data = response.json()
        tracks = [
            {
                "track_name": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
                "release_date": track["album"]["release_date"],
                "album_type": track["album"]["album_type"],
            }
            for track in search_data["tracks"]["items"]
        ]
        return tracks
    else:
        return Response(
            {"error": "Error al obtener las canciones."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def add_preferences(request, user_id: int, track: str, artist: str):
    """
    Agrega una preferencia musical a un usuario existente en la base de datos.

    Args:
        request (HttpRequest): Objeto de solicitud HTTP.
        user_id (int): El id del usuario al que se va a agregar la preferencia.
        track (str): El nombre de la canción.
        artist (str): El nombre del artista de la canción.

    Returns:
        Response: Una respuesta HTTP que contiene un mensaje de confirmación y
        el usuario actualizado con sus preferencias musicales.
    """
    user = User.objects.get(id=user_id)

    access_token = get_spotify_token()

    track_info = get_track_info(access_token, track, artist)

    user.preferences.append(
        {
            "track_info": track_info,
        }
    )
    user.save()
    return Response(
        {
            "message": "Preferencias agregadas correctamente",
            "Usuario actualizado": {
                "name": user.name,
                "email": user.email,
                "preferences": user.preferences,
            },
        },
        status=status.HTTP_200_OK,
    )


def get_top_artists(
    access_token: str, limit: int = 10, time_range: str = "medium_term"
):
    """
    Obtiene los artistas más escuchados del usuario autenticado.

    Args:
        access_token (str): El token de acceso del usuario.
        limit (int, optional): El número de artistas a obtener. Defaults to 10.
        time_range (str, optional): El rango de tiempo para obtener los artistas
            más escuchados. Los valores posibles son "short_term", "medium_term"
            o "long_term". Defaults to "medium_term".

    Returns:
        dict: Un diccionario con una lista de artistas y sus géneros.

    Raises:
        Response: Si ocurre un error al obtener los artistas.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}

    response = requests.get(SPOTIFY_API_URL, headers=headers, params=params)
    if response.status_code == 200:
        artists_data = response.json()
        artists = [
            {
                "name": artist["name"],
                "genres": artist["genres"],
            }
            for artist in artists_data["items"]
        ]
        return {"top_artists": artists}
    else:
        return Response(
            {"error": "Error al obtener los artistas"},
            status=status.HTTP_400_BAD_REQUEST,
        )


def get_top_tracks(access_token: str, limit: int = 10, time_range: str = "medium_term"):
    """
    Obtiene las canciones más escuchadas del usuario autenticado desde Spotify.

    Args:
        access_token (str): El token de acceso del usuario.
        limit (int, optional): El número de canciones a obtener. Defaults to 10.
        time_range (str, optional): El rango de tiempo para obtener las canciones
            más escuchadas. Los valores posibles son "short_term", "medium_term"
            o "long_term". Defaults to "medium_term".

    Returns:
        dict: Un diccionario con una lista de canciones y sus detalles.

    Raises:
        Response: Si ocurre un error al obtener las canciones.
    """
    url = "https://api.spotify.com/v1/me/top/tracks"

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"limit": limit, "time_range": time_range}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        tracks_data = response.json()
        tracks = [
            {
                "track_name": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
            }
            for track in tracks_data["items"]
        ]
        return {"top_tracks": tracks}
    else:
        raise Response(
            {"error": "Error al obtener las canciones"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_user_info(request):
    """
    Obtiene la información de las canciones y artistas más escuchados del usuario autenticado.

    Returns:
        dict: Un diccionario con una lista de canciones y una lista de artistas.

    Raises:
        Response: Si ocurre un error al obtener las canciones o artistas.
    """
    access_token = get_spotify_token()
    return Response(
        {
            "Canciones más escuchadas": get_top_tracks(access_token),
            "Artistas más escuchados": get_top_artists(access_token),
        },
        status=status.HTTP_200_OK,
    )
