"""Item 9 do docs/HTR_PLANO_EXECUCAO.md: o recorte precisa existir em disco.

Ate agora `answer_crop_path` guardava a string `batch=.../page=.../q=...` -- uma
referencia para um arquivo que nunca foi gravado. A tela de revisao exibia essa
string. Corrigir quatro palavras de cursiva olhando a imagem leva tres segundos;
sem imagem o revisor nao revisa, ele aceita.
"""

from uuid import uuid4

import pytest
from PIL import Image

from app.core import storage


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "UPLOAD_DIR", tmp_path)
    return tmp_path


def _png_bytes(size=(120, 40)) -> bytes:
    import io

    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 210, 230)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_write_answer_crop_returns_a_local_url():
    url = storage.write_answer_crop(uuid4(), 3, 2, _png_bytes())

    assert url.startswith("local:")


def test_written_crop_can_be_read_back_as_an_image():
    batch = uuid4()
    url = storage.write_answer_crop(batch, 3, 2, _png_bytes(size=(120, 40)))

    with Image.open(storage.path_from_local_url(url)) as img:
        assert img.size == (120, 40)


def test_crop_path_encodes_batch_page_and_question(upload_dir):
    batch = uuid4()
    url = storage.write_answer_crop(batch, 7, 4, _png_bytes())

    path = storage.path_from_local_url(url)
    assert str(batch) in path.as_posix()
    assert "p007" in path.name
    assert "q004" in path.name


def test_rewriting_the_same_crop_overwrites_instead_of_duplicating(upload_dir):
    batch = uuid4()
    first = storage.write_answer_crop(batch, 1, 1, _png_bytes(size=(10, 10)))
    second = storage.write_answer_crop(batch, 1, 1, _png_bytes(size=(20, 20)))

    assert first == second
    with Image.open(storage.path_from_local_url(second)) as img:
        assert img.size == (20, 20)


def test_crops_of_different_questions_do_not_collide(upload_dir):
    batch = uuid4()

    assert storage.write_answer_crop(batch, 1, 1, _png_bytes()) != storage.write_answer_crop(
        batch, 1, 2, _png_bytes()
    )


@pytest.mark.parametrize(
    "hostile",
    [
        "local:../../../etc/passwd",
        "local:batches/../../secret.pdf",
        "local:..\\..\\windows\\system32\\config\\sam",
        # `Path(base) / "C:/..."` descarta a base e devolve o caminho da direita.
        "local:C:/Windows/System32/config/sam",
        "local:C:\\Windows\\System32\\config\\sam",
    ],
)
def test_path_from_local_url_refuses_to_escape_the_upload_root(hostile):
    """O caminho vem do banco; trata-lo como confiavel seria leitura arbitraria de disco."""
    with pytest.raises(ValueError):
        storage.path_from_local_url(hostile)


@pytest.mark.parametrize(
    "url",
    [
        "local:/crops/x.png",
        # UNC: as barras iniciais caem e o resto vira caminho relativo, dentro da raiz.
        "local://servidor/share/segredo.png",
        "local:\\\\servidor\\share\\segredo.png",
    ],
)
def test_leading_separators_are_stripped_into_a_path_inside_the_root(url):
    """`local:/x.png` e o arquivo x.png DENTRO da raiz, nunca /x.png do sistema."""
    assert storage.upload_root() in storage.path_from_local_url(url).parents


def test_path_from_local_url_rejects_non_local_scheme():
    with pytest.raises(ValueError):
        storage.path_from_local_url("https://exemplo.com/arquivo.png")


def test_legitimate_batch_path_still_resolves():
    batch = uuid4()
    url = storage.write_batch_pdf(batch, b"%PDF-1.4 fake")

    assert storage.path_from_local_url(url).read_bytes().startswith(b"%PDF")
