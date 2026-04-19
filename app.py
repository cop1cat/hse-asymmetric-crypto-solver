import math
import streamlit as st


st.set_page_config(page_title="Крипто-решалка", layout="wide")


def init_state() -> None:
    defaults = {
        "rsa_n_val": None,
        "rsa_d_val": None,
        "rsa_p_val": None,
        "rsa_q_val": None,
        "rsa_e_val": None,
        "rsa_last_ciphers": None,
        "eg_x_val": None,
        "eg_p_val": None,
        "eg_last_ciphers": None,
        "eg_x_sig_val": None,
        "eg_p_sig_val": None,
        "eg_g_sig_val": None,
        "eg_y_sig_val": None,
        "eg_p_hash_val": None,
        "eg_r_hash_val": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────
#  АЛФАВИТ
# ─────────────────────────────────────────────

def default_alphabet_str() -> str:
    return ", ".join(f"{chr(i + 64)}={i}" for i in range(1, 27))


def build_alphabet(alphabet_str: str) -> dict:
    result = {}
    for pair in alphabet_str.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        letter, code = pair.split("=")
        result[letter.strip().upper()] = int(code.strip())
    return result


def encode_message(message: str, alphabet: dict) -> list:
    return [alphabet[ch] for ch in message.upper() if ch in alphabet]


def decode_message(codes: list, alphabet: dict) -> str:
    reverse = {v: k for k, v in alphabet.items()}
    return "".join(reverse.get(c, f"[{c}]") for c in codes)


# ─────────────────────────────────────────────
#  МАТЕМАТИКА
# ─────────────────────────────────────────────

def extended_gcd(a: int, b: int):
    if b == 0:
        return a, 1, 0
    g, x, y = extended_gcd(b, a % b)
    return g, y, x - (a // b) * y


def mod_inverse(a: int, m: int):
    g, x, _ = extended_gcd(a % m, m)
    if g != 1:
        return None
    return x % m


def gcd_steps(a: int, b: int):
    steps = []
    while b != 0:
        q, r = divmod(a, b)
        steps.append((a, b, q, r))
        a, b = b, r
    return steps


def reverse_pass_lines(a_init: int, m_init: int):
    """Обратный ход РАЕ: возвращает (список LaTeX-строк, обратный элемент).

    Каждая строка — очередной шаг подстановки снизу вверх. Ответ — коэффициент
    при a_init в финальном разложении 1 = x·m_init + y·a_init, приведённый по mod m_init.
    """
    steps = []
    A, B = m_init, a_init
    while B != 0:
        q, r = divmod(A, B)
        steps.append((A, B, q, r))
        A, B = B, r
    if not steps or steps[-1][3] != 0:
        return [], None
    gcd = steps[-1][1]
    if gcd != 1:
        return [], None
    if len(steps) < 2:
        return [f"1 = 0 \\cdot {m_init} + 1 \\cdot {a_init}"], 1 % m_init

    idx = len(steps) - 2
    A0, B0, q0, _ = steps[idx]
    c_big, c_small = 1, -q0
    big, small = A0, B0
    lines = [f"1 = {A0} - {B0} \\cdot {q0}"]

    for i in range(idx - 1, -1, -1):
        A_i, B_i, q_i, r_i = steps[i]
        if small != r_i:
            break
        new_c_big = c_small
        new_c_small = c_big - c_small * q_i
        sub_expr = (
            f"1 = {c_big} \\cdot {big} + ({c_small}) \\cdot ({A_i} - {B_i} \\cdot {q_i})"
        )
        big, small = A_i, B_i
        c_big, c_small = new_c_big, new_c_small
        lines.append(sub_expr)
        lines.append(f"1 = {c_big} \\cdot {big} + ({c_small}) \\cdot {small}")

    inv = c_small % m_init
    return lines, inv


def fast_pow_steps(base: int, exp: int, mod: int):
    bits = bin(exp)[2:]
    steps = []
    result = base % mod
    for bit in bits[1:]:
        sq = (result * result) % mod
        if bit == "1":
            mul = (sq * base) % mod
            steps.append({"bit": bit, "prev": result, "sq": sq, "mul": mul, "result": mul})
            result = mul
        else:
            steps.append({"bit": bit, "prev": result, "sq": sq, "mul": None, "result": sq})
            result = sq
    return result, steps


def poly_hash(codes: list, r: int, p: int):
    steps = []
    h = 0
    for i, m_i in enumerate(codes):
        h_new = (r * h + m_i) % p
        steps.append((i + 1, h, m_i, h_new))
        h = h_new
    H = (r * h) % p
    return H, steps


def fermat_factorization(n: int):
    steps = []
    a = math.isqrt(n)
    if a * a < n:
        a += 1
    for _ in range(100000):
        b2 = a * a - n
        b = math.isqrt(b2)
        steps.append((a, b2, b, b * b == b2))
        if b * b == b2:
            return a - b, a + b, steps
        a += 1
    return None


# ─────────────────────────────────────────────
#  UI — ПРИМИТИВЫ
# ─────────────────────────────────────────────

def _text(md: str) -> None:
    st.markdown(md)


def _latex(expr: str) -> None:
    st.latex(expr)


def _ok(msg: str) -> None:
    st.success(msg)


def _info(msg: str) -> None:
    st.info(msg)


def _err(msg: str) -> None:
    st.error(msg)


def _section(title: str) -> None:
    st.markdown(f"---\n**{title}**")


# ─────────────────────────────────────────────
#  UI — АЛГОРИТМЫ
# ─────────────────────────────────────────────

def ui_mod_inverse(a: int, m: int, var: str = "x"):
    a_mod = a % m
    st.markdown(
        f"Ищем **{var} = {a}⁻¹ mod {m}** — такое {var}, что "
        f"${a} \\cdot {var} \\equiv 1 \\pmod{{{m}}}$.\n\n"
        f"**Прямой ход** — делим с остатком, пока не получим 0:"
    )
    steps = gcd_steps(m, a_mod)
    forward_md = "\n\n".join(
        f"$${s_a} = {s_b} \\cdot {s_q} + {s_r}$$" for s_a, s_b, s_q, s_r in steps
    )
    st.markdown(forward_md)

    if math.gcd(a_mod, m) != 1:
        _err(f"НОД({a}, {m}) ≠ 1 — обратного элемента не существует.")
        return None

    lines, inv = reverse_pass_lines(a_mod, m)
    if inv is None:
        _err("Не удалось восстановить обратный элемент.")
        return None

    st.markdown(
        "**Обратный ход** — выражаем 1 подстановкой снизу вверх:\n\n"
        + "\n\n".join(f"$${ln}$$" for ln in lines)
    )
    st.markdown(
        f"Значит ${a_mod}^{{-1}} \\equiv {inv} \\pmod{{{m}}}$. "
        f"Проверка: ${a_mod} \\cdot {inv} = {a_mod * inv} = "
        f"{m} \\cdot {(a_mod * inv) // m} + 1$ ✓"
    )
    _ok(f"**{var} = {inv}**")
    return inv


def ui_fast_pow(base: int, exp: int, mod: int, var: str = "результат") -> int:
    bits = bin(exp)[2:]
    result_final, steps = fast_pow_steps(base, exp, mod)

    lines = [f"$${exp} = {bits}_2$$", f"$$\\text{{старт}}: r = {base} \\bmod {mod} = {base % mod}$$"]
    for s in steps:
        lines.append(
            f"$$\\text{{бит {s['bit']}:}}\\quad {s['prev']}^2 \\bmod {mod} = {s['sq']}$$"
        )
        if s["mul"] is not None:
            lines.append(
                f"$$\\quad\\text{{×основание:}}\\quad {s['sq']} \\cdot {base} \\bmod {mod} = {s['mul']}$$"
            )

    st.markdown(
        f"Вычисляем ${base}^{{{exp}}} \\bmod {mod}$ быстрым возведением. "
        f"Идём по битам слева направо (пропуская первый): квадрат, и если бит = 1 — ×основание.\n\n"
        + "\n\n".join(lines)
    )
    _ok(f"**{var} = {base}^{exp} mod {mod} = {result_final}**")
    return result_final


def ui_hash(codes: list, letters: str, r: int, p: int) -> int:
    H, steps = poly_hash(codes, r, p)
    h_last = steps[-1][3] if steps else 0

    lines = [
        r"$$h_0 = 0, \quad h_i = (r \cdot h_{i-1} + m_i) \bmod p, \quad H = r \cdot h_t \bmod p$$",
        r"$$h_0 = 0$$",
    ]
    for i, h_prev, m_i, h_new in steps:
        lines.append(
            f"$$h_{{{i}}} = ({r} \\cdot {h_prev} + {m_i}) \\bmod {p} "
            f"= {r * h_prev + m_i} \\bmod {p} = {h_new}$$"
        )
    lines.append(
        f"$$H = {r} \\cdot {h_last} \\bmod {p} = {r * h_last % p}$$"
    )

    st.markdown(
        f"Хэш слова **{letters}**, $r = {r}$, $p = {p}$. "
        f"Коды букв: {dict(zip(letters, codes))}.\n\n" + "\n\n".join(lines)
    )
    _ok(f"**H({letters}) = {H}**")
    return H


# ─────────────────────────────────────────────
#  ЗАДАЧИ — RSA
# ─────────────────────────────────────────────

def solve_rsa_keygen(p: int, q: int, e: int):
    _section("Шаг 1. Вычисляем n и φ(n)")
    n = p * q
    phi = (p - 1) * (q - 1)
    _text("Модуль RSA:")
    _latex(f"n = p \\cdot q = {p} \\cdot {q} = {n}")
    _text("Функция Эйлера:")
    _latex(f"\\phi(n) = (p-1)(q-1) = {p-1} \\cdot {q-1} = {phi}")

    _section("Шаг 2. Находим секретную экспоненту d")
    gcd_val = math.gcd(e, phi)
    _text(f"Проверяем: $\\gcd({e},\\, {phi}) = {gcd_val}$.")
    if gcd_val != 1:
        _err(f"НОД({e}, {phi}) ≠ 1. Выберите другое e.")
        return None
    _text("НОД = 1 ✓, обратный элемент существует.")

    d = ui_mod_inverse(e, phi, "d")
    if d is None:
        return None

    _section("Итог")
    _ok(f"Открытый ключ: $PK = (e={e},\\ n={n})$")
    _ok(f"Закрытый ключ: $SK = (d={d},\\ p={p},\\ q={q})$")
    return n, phi, d


def solve_rsa_encrypt(message: str, e: int, n: int, alphabet: dict) -> list:
    codes = encode_message(message, alphabet)
    _text("Шифруем каждую букву по формуле:")
    _latex(r"c_i = m_i^e \bmod n")
    _text(
        f"Параметры: $e = {e}$, $n = {n}$. "
        f"Кодируем **{message.upper()}**: {dict(zip(message.upper(), codes))}."
    )
    ciphers = []
    for ch, m_i in zip(message.upper(), codes):
        _section(f"Буква «{ch}» = {m_i}")
        c_i = ui_fast_pow(m_i, e, n, f"c({ch})")
        ciphers.append(c_i)

    _info(f"Шифртекст: $C = {ciphers}$")
    return ciphers


def solve_rsa_decrypt_crt(ciphers: list, d: int, p: int, q: int, n: int, alphabet: dict) -> list:
    _text(
        "Расшифровываем через **КТО**. "
        "Вместо $c^d \\bmod n$ считаем отдельно по модулям $p$ и $q$."
    )

    _section("Шаг 1. Вычисляем dp и dq")
    _text("По теореме Эйлера показатель $d$ можно уменьшить:")
    dp = d % (p - 1)
    dq = d % (q - 1)
    _latex(f"d_p = d \\bmod (p-1) = {d} \\bmod {p-1} = {dp}")
    _latex(f"d_q = d \\bmod (q-1) = {d} \\bmod {q-1} = {dq}")

    _section("Шаг 2. Вспомогательные обратные элементы")
    q_inv_p = ui_mod_inverse(q, p, f"{q}^{{-1}} \\bmod {p}")
    p_inv_q = ui_mod_inverse(p, q, f"{p}^{{-1}} \\bmod {q}")
    if q_inv_p is None or p_inv_q is None:
        return []

    decoded = []
    for i, c_i in enumerate(ciphers):
        _section(f"Символ {i+1}: c = {c_i}")
        c_mod_p = c_i % p
        c_mod_q = c_i % q
        _text("Уменьшаем основание:")
        _latex(
            f"{c_i} \\bmod {p} = {c_mod_p}, \\qquad "
            f"{c_i} \\bmod {q} = {c_mod_q}"
        )
        _text("Частичный остаток $x = c^{d_p} \\bmod p$:")
        x = ui_fast_pow(c_mod_p, dp, p, "x")
        _text("Частичный остаток $y = c^{d_q} \\bmod q$:")
        y = ui_fast_pow(c_mod_q, dq, q, "y")
        _text("Восстанавливаем $m$ по формуле КТО:")
        _latex(
            r"m = x \cdot q \cdot (q^{-1} \bmod p)"
            r" + y \cdot p \cdot (p^{-1} \bmod q) \pmod{n}"
        )
        m_val = (x * q * q_inv_p + y * p * p_inv_q) % n
        _latex(
            f"m = {x} \\cdot {q} \\cdot {q_inv_p}"
            f" + {y} \\cdot {p} \\cdot {p_inv_q}"
            f" \\bmod {n} = {x*q*q_inv_p + y*p*p_inv_q} \\bmod {n} = {m_val}"
        )
        letter = decode_message([m_val], alphabet)
        _ok(f"$m = {m_val}$ → буква **«{letter}»**")
        decoded.append(m_val)

    word = decode_message(decoded, alphabet)
    _info(f"Расшифровано: **{word}**")
    return decoded


def solve_rsa_sign(H: int, d: int, n: int) -> int:
    _text("Создаём RSA-подпись по формуле:")
    _latex(r"S = H^d \bmod n")
    S = ui_fast_pow(H, d, n, "S")
    _ok(f"**Подпись $S = {S}$**")
    return S


def solve_rsa_verify(message: str, S_ver: int, e: int, n: int, r_hash: int, p_hash: int, alphabet: dict) -> None:
    _text(f"Проверяем RSA-подпись $S = {S_ver}$ для сообщения **{message.upper()}**.")
    _latex(r"S^e \bmod n = H \quad ?")

    _section("Шаг 1. Вычисляем хэш сообщения")
    codes = encode_message(message, alphabet)
    H = ui_hash(codes, message.upper(), r_hash, p_hash)

    _section("Шаг 2. Восстанавливаем хэш из подписи")
    restored = ui_fast_pow(S_ver, e, n, "S^e \\bmod n")

    if restored == H:
        _ok(f"${restored} = {H}$ — **подпись верна ✓**")
    else:
        st.error(f"${restored} \\neq {H}$ — подпись неверна ✗")


# ─────────────────────────────────────────────
#  ЗАДАЧИ — ЭЛЬ-ГАМАЛЬ
# ─────────────────────────────────────────────

def solve_elgamal_find_x(p: int, g: int, y: int):
    lines = []
    val = 1
    found = None
    for candidate in range(1, p):
        val = (val * g) % p
        lines.append(f"$${g}^{{{candidate}}} \\bmod {p} = {val}$$")
        if val == y:
            found = candidate
            break

    st.markdown(
        f"Находим $x$ из уравнения ${g}^x \\equiv {y} \\pmod{{{p}}}$. "
        f"Перебираем $x$ от 1 до $p-1$:\n\n" + "\n\n".join(lines)
    )
    if found is not None:
        _ok(f"**x = {found}**")
        return found
    _err("Секретный ключ не найден. Проверьте параметры.")
    return None


def solve_elgamal_encrypt(message: str, p: int, g: int, y: int, k_list: list, alphabet: dict) -> list:
    codes = encode_message(message, alphabet)
    _text("Шифруем каждую букву по формулам:")
    _latex(r"a = g^k \bmod p, \qquad b = m \cdot y^k \bmod p")
    _text(
        f"Параметры: $p = {p}$, $g = {g}$, $y = {y}$. "
        f"Кодируем **{message.upper()}**: {dict(zip(message.upper(), codes))}."
    )
    ciphers = []
    for i, (ch, m_i) in enumerate(zip(message.upper(), codes)):
        k = k_list[i] if i < len(k_list) else 1
        _section(f"Буква «{ch}» = {m_i}, k = {k}")
        a = pow(g, k, p)
        _text("Вычисляем $a = g^k \\bmod p$:")
        _latex(f"a = {g}^{{{k}}} \\bmod {p} = {a}")
        yk = pow(y, k, p)
        b = (m_i * yk) % p
        _text("Вычисляем $b = m \\cdot y^k \\bmod p$:")
        _latex(
            f"b = {m_i} \\cdot {y}^{{{k}}} \\bmod {p}"
            f" = {m_i} \\cdot {yk} \\bmod {p} = {b}"
        )
        _ok(f"Шифртекст «{ch}»: $({a},\\ {b})$")
        ciphers.append((a, b))

    _info(f"Итоговый шифртекст: $C = {ciphers}$")
    return ciphers


def solve_elgamal_decrypt(ciphers: list, x: int, p: int, alphabet: dict) -> list:
    _text("Расшифровываем по формуле:")
    _latex(r"m = b \cdot (a^x)^{-1} \bmod p")
    _text(f"Секретный ключ $x = {x}$.")

    decoded = []
    for i, (a, b) in enumerate(ciphers):
        _section(f"Символ {i+1}: $({a},\\ {b})$")
        _text("Вычисляем $a^x \\bmod p$:")
        ax = pow(a, x, p)
        _latex(f"a^x = {a}^{{{x}}} \\bmod {p} = {ax}")
        _text("Находим обратный $(a^x)^{-1} \\bmod p$:")
        ax_inv = ui_mod_inverse(ax, p, "(a^x)^{-1}")
        if ax_inv is None:
            continue
        m_val = (b * ax_inv) % p
        _text("Восстанавливаем $m$:")
        _latex(f"m = {b} \\cdot {ax_inv} \\bmod {p} = {m_val}")
        letter = decode_message([m_val], alphabet)
        _ok(f"$m = {m_val}$ → буква **«{letter}»**")
        decoded.append(m_val)

    word = decode_message(decoded, alphabet)
    _info(f"Расшифровано: **{word}**")
    return decoded


def solve_elgamal_sign(H: int, x: int, k: int, p: int, g: int):
    _text(
        f"Создаём подпись для хэша $H = {H}$. "
        f"Параметры: $p = {p}$, $g = {g}$, $x = {x}$, $k = {k}$."
    )
    gcd_val = math.gcd(k, p - 1)
    _text(f"Проверяем: $\\gcd({k},\\ {p-1}) = {gcd_val}$.")
    if gcd_val != 1:
        _err(f"НОД({k}, {p-1}) ≠ 1. Выберите другой k.")
        return None
    _text("НОД = 1 ✓")

    _section("Шаг 1. Вычисляем R")
    R = pow(g, k, p)
    _latex(f"R = {g}^{{{k}}} \\bmod {p} = {R}")

    _section(f"Шаг 2. Находим $k^{{-1}} \\bmod (p-1)$")
    _text(f"Обратный к $k$ берём по модулю $p-1 = {p-1}$:")
    k_inv = ui_mod_inverse(k, p - 1, "k^{-1}")
    if k_inv is None:
        return None

    _section("Шаг 3. Вычисляем S")
    _latex(r"S = (H - x \cdot R) \cdot k^{-1} \bmod (p-1)")
    S_raw = (H - x * R) * k_inv
    S = S_raw % (p - 1)
    _latex(
        f"S = ({H} - {x} \\cdot {R}) \\cdot {k_inv} \\bmod {p-1}"
        f" = {H - x*R} \\cdot {k_inv} \\bmod {p-1}"
        f" = {S_raw} \\bmod {p-1} = {S}"
    )
    _ok(f"**Подпись: $(R, S) = ({R},\\ {S})$**")
    return R, S


def solve_elgamal_verify(message: str, R_ver: int, S_ver: int, p: int, g: int, y: int, r_hash: int, p_hash: int, alphabet: dict) -> None:
    _text(
        f"Проверяем подпись $(R, S) = ({R_ver},\\ {S_ver})$ "
        f"для сообщения **{message.upper()}**."
    )
    _latex(r"y^R \cdot R^S \equiv g^H \pmod{p}")

    _section("Шаг 1. Вычисляем хэш")
    codes = encode_message(message, alphabet)
    H = ui_hash(codes, message.upper(), r_hash, p_hash)

    _section("Шаг 2. Проверяем равенство")
    lhs = (pow(y, R_ver, p) * pow(R_ver, S_ver, p)) % p
    rhs = pow(g, H, p)
    _text("Левая часть:")
    _latex(
        f"y^R \\cdot R^S \\bmod p = "
        f"{y}^{{{R_ver}}} \\cdot {R_ver}^{{{S_ver}}} \\bmod {p} = {lhs}"
    )
    _text("Правая часть:")
    _latex(f"g^H \\bmod p = {g}^{{{H}}} \\bmod {p} = {rhs}")

    if lhs == rhs:
        _ok(f"${lhs} = {rhs}$ — **подпись верна ✓**")
    else:
        st.error(f"${lhs} \\neq {rhs}$ — подпись неверна ✗")


# ─────────────────────────────────────────────
#  УТИЛИТЫ
# ─────────────────────────────────────────────

def solve_fermat(N: int) -> None:
    _text(
        f"Факторизуем $N = {N}$ методом Ферма. "
        f"Ищем $a$ и $b$: $N = a^2 - b^2$, тогда $P = a-b$, $Q = a+b$."
    )
    a_start = math.isqrt(N)
    if a_start * a_start < N:
        a_start += 1
    _text(f"Начинаем с $a = \\lceil\\sqrt{{{N}}}\\rceil = {a_start}$.")
    _latex(r"b^2 = a^2 - N, \quad b = \sqrt{b^2} \text{ (проверяем целость)}")

    result = fermat_factorization(N)
    if result is None:
        _err("Не удалось факторизовать за разумное число шагов.")
        return

    P, Q, steps = result
    for a, b2, b, found in steps:
        check = "✓" if found else "✗"
        _latex(
            f"a = {a}:\\quad b^2 = {a}^2 - {N} = {b2},"
            f"\\quad b \\approx {b} \\quad {check}"
        )
        if found:
            break

    a_final = steps[-1][0]
    b_final = math.isqrt(steps[-1][1])
    _latex(f"P = {a_final} - {b_final} = {P}")
    _latex(f"Q = {a_final} + {b_final} = {Q}")
    _latex(f"P \\cdot Q = {P} \\cdot {Q} = {P * Q} = N \\quad ✓")
    _ok(f"**Множители: P = {P}, Q = {Q}**")


# ─────────────────────────────────────────────
#  ВКЛАДКИ
# ─────────────────────────────────────────────

def tab_rsa(alphabet: dict) -> None:
    st.header("RSA")

    with st.expander("⚙️ Параметры RSA", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p = st.number_input("p", value=31, step=1, key="rsa_p_input")
        with col2:
            q = st.number_input("q", value=23, step=1, key="rsa_q_input")
        with col3:
            e = st.number_input("e", value=7, step=1, key="rsa_e_input")

    p, q, e = int(p), int(q), int(e)

    st.subheader("1. Генерация ключей")
    if st.button("Сгенерировать ключи", key="rsa_keygen"):
        result = solve_rsa_keygen(p, q, e)
        if result:
            n, phi, d = result
            st.session_state["rsa_n_val"] = n
            st.session_state["rsa_d_val"] = d
            st.session_state["rsa_p_val"] = p
            st.session_state["rsa_q_val"] = q
            st.session_state["rsa_e_val"] = e

    st.subheader("2. Шифрование")
    msg_enc = st.text_input("Открытый текст", value="RAIN", key="rsa_msg_enc")
    if st.button("Зашифровать", key="rsa_enc"):
        if st.session_state.get("rsa_n_val") is None:
            st.warning("Сначала сгенерируйте ключи.")
        else:
            ciphers = solve_rsa_encrypt(
                msg_enc,
                st.session_state["rsa_e_val"],
                st.session_state["rsa_n_val"],
                alphabet,
            )
            st.session_state["rsa_last_ciphers"] = ciphers

    st.subheader("3. Расшифрование (КТО)")
    cipher_input = st.text_input(
        "Шифртекст через запятую", value="128,333,333,168", key="rsa_cipher_in"
    )
    if st.button("Расшифровать", key="rsa_dec"):
        if st.session_state.get("rsa_n_val") is None:
            st.warning("Сначала сгенерируйте ключи.")
        else:
            cipher_list = [int(x.strip()) for x in cipher_input.split(",")]
            solve_rsa_decrypt_crt(
                cipher_list,
                st.session_state["rsa_d_val"],
                st.session_state["rsa_p_val"],
                st.session_state["rsa_q_val"],
                st.session_state["rsa_n_val"],
                alphabet,
            )

    st.subheader("4. ЭЦП RSA")
    with st.expander("Параметры хэша и подписи", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            p_hash = st.number_input("p_hash", value=13, step=1, key="rsa_ph_input")
            r_hash = st.number_input("r (хэш)", value=5, step=1, key="rsa_rh_input")
        with col2:
            msg_sign = st.text_input(
                "Сообщение для подписи", value="RAIN", key="rsa_msign_input"
            )

    if st.button("Вычислить хэш + создать подпись", key="rsa_sign"):
        if st.session_state.get("rsa_n_val") is None:
            st.warning("Сначала сгенерируйте ключи.")
        else:
            _section("Хэш сообщения")
            codes = encode_message(msg_sign, alphabet)
            H = ui_hash(codes, msg_sign.upper(), int(r_hash), int(p_hash))
            _section("Создаём подпись")
            solve_rsa_sign(
                H,
                st.session_state["rsa_d_val"],
                st.session_state["rsa_n_val"],
            )

    st.markdown("**Верификация:**")
    col3, col4 = st.columns(2)
    with col3:
        msg_ver = st.text_input("Сообщение", value="BOOK", key="rsa_mver_input")
    with col4:
        s_ver = st.number_input("S_ver", value=1, step=1, key="rsa_sver_input")

    if st.button("Верифицировать", key="rsa_verify"):
        if st.session_state.get("rsa_n_val") is None:
            st.warning("Сначала сгенерируйте ключи.")
        else:
            solve_rsa_verify(
                msg_ver,
                int(s_ver),
                st.session_state["rsa_e_val"],
                st.session_state["rsa_n_val"],
                int(r_hash),
                int(p_hash),
                alphabet,
            )


def tab_elgamal(alphabet: dict) -> None:
    st.header("Эль-Гамаль")

    with st.expander("⚙️ Параметры Эль-Гамаль", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p = st.number_input("p", value=31, step=1, key="eg_p_input")
        with col2:
            g = st.number_input("g", value=3, step=1, key="eg_g_input")
        with col3:
            y = st.number_input("y (откр. ключ)", value=27, step=1, key="eg_y_input")

    p, g, y = int(p), int(g), int(y)

    st.subheader("1. Нахождение секретного ключа x")
    if st.button("Найти x", key="eg_findx"):
        x = solve_elgamal_find_x(p, g, y)
        if x is not None:
            st.session_state["eg_x_val"] = x
            st.session_state["eg_p_val"] = p

    st.subheader("2. Шифрование")
    col1, col2 = st.columns(2)
    with col1:
        msg_enc = st.text_input("Открытый текст", value="FISH", key="eg_msg_enc")
    with col2:
        k_input = st.text_input(
            "Сессионные ключи k (через запятую)", value="3,5,7,9", key="eg_ks_input"
        )
    if st.button("Зашифровать", key="eg_enc"):
        if st.session_state.get("eg_x_val") is None:
            st.warning("Сначала найдите x.")
        else:
            k_list = [int(v.strip()) for v in k_input.split(",")]
            ciphers = solve_elgamal_encrypt(msg_enc, p, g, y, k_list, alphabet)
            st.session_state["eg_last_ciphers"] = ciphers

    st.subheader("3. Расшифрование")
    cipher_input = st.text_input(
        "Шифртекст: пары через ';', числа через ','. Пример: 24,26;24,29",
        value="24,26;24,29;17,11;24,3",
        key="eg_cin_input",
    )
    if st.button("Расшифровать", key="eg_dec"):
        if st.session_state.get("eg_x_val") is None:
            st.warning("Сначала найдите x.")
        else:
            pairs = []
            for pair in cipher_input.split(";"):
                a_s, b_s = pair.strip().split(",")
                pairs.append((int(a_s), int(b_s)))
            solve_elgamal_decrypt(
                pairs,
                st.session_state["eg_x_val"],
                st.session_state["eg_p_val"],
                alphabet,
            )

    st.subheader("4. ЭЦП Эль-Гамаль")
    with st.expander("Параметры подписи", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p_sig = st.number_input("p_sig", value=37, step=1, key="eg_psig_input")
            g_sig = st.number_input("g_sig", value=2, step=1, key="eg_gsig_input")
        with col2:
            y_sig = st.number_input("y_sig", value=17, step=1, key="eg_ysig_input")
            k_sig = st.number_input(
                "k (сессионный)", value=11, step=1, key="eg_ksig_input"
            )
        with col3:
            p_hash = st.number_input("p_hash", value=13, step=1, key="eg_ph_input")
            r_hash = st.number_input("r (хэш)", value=5, step=1, key="eg_rh_input")

    msg_sign = st.text_input(
        "Сообщение для подписи", value="RAIN", key="eg_msign_input"
    )

    if st.button("Вычислить хэш + создать подпись", key="eg_sign"):
        p_sig_i = int(p_sig)
        g_sig_i = int(g_sig)
        y_sig_i = int(y_sig)
        p_hash_i = int(p_hash)
        r_hash_i = int(r_hash)

        _section("Шаг 1. Находим x для подписи")
        x_sig = solve_elgamal_find_x(p_sig_i, g_sig_i, y_sig_i)
        if x_sig is not None:
            st.session_state.update({
                "eg_x_sig_val": x_sig,
                "eg_p_sig_val": p_sig_i,
                "eg_g_sig_val": g_sig_i,
                "eg_y_sig_val": y_sig_i,
                "eg_p_hash_val": p_hash_i,
                "eg_r_hash_val": r_hash_i,
            })
            _section("Шаг 2. Хэш сообщения")
            codes = encode_message(msg_sign, alphabet)
            H = ui_hash(codes, msg_sign.upper(), r_hash_i, p_hash_i)

            _section("Шаг 3. Создаём подпись")
            solve_elgamal_sign(H, x_sig, int(k_sig), p_sig_i, g_sig_i)

    st.markdown("**Верификация:**")
    col3, col4, col5 = st.columns(3)
    with col3:
        msg_ver = st.text_input("Сообщение", value="BOOK", key="eg_mver_input")
    with col4:
        r_ver = st.number_input("R_ver", value=13, step=1, key="eg_rver_input")
    with col5:
        s_ver = st.number_input("S_ver", value=25, step=1, key="eg_sver_input")

    if st.button("Верифицировать", key="eg_verify"):
        if st.session_state.get("eg_x_sig_val") is None:
            st.warning("Сначала создайте подпись чтобы загрузить параметры.")
        else:
            solve_elgamal_verify(
                msg_ver,
                int(r_ver),
                int(s_ver),
                st.session_state["eg_p_sig_val"],
                st.session_state["eg_g_sig_val"],
                st.session_state["eg_y_sig_val"],
                st.session_state["eg_r_hash_val"],
                st.session_state["eg_p_hash_val"],
                alphabet,
            )


def tab_utils(alphabet: dict) -> None:
    st.header("Утилиты")

    st.subheader("Полиномиальный хэш")
    col1, col2, col3 = st.columns(3)
    with col1:
        h_msg = st.text_input("Сообщение", value="RAIN", key="util_hmsg_input")
    with col2:
        h_r = st.number_input("r", value=5, step=1, key="util_hr_input")
    with col3:
        h_p = st.number_input("p", value=13, step=1, key="util_hp_input")
    if st.button("Вычислить хэш", key="util_hash"):
        codes = encode_message(h_msg, alphabet)
        ui_hash(codes, h_msg.upper(), int(h_r), int(h_p))

    st.divider()
    st.subheader("Факторизация Ферма")
    ferm_n = st.number_input("N", value=2021, step=1, key="util_ferm_input")
    if st.button("Факторизовать", key="util_ferm_btn"):
        solve_fermat(int(ferm_n))

    st.divider()
    st.subheader("Расширенный алгоритм Евклида")
    col1, col2 = st.columns(2)
    with col1:
        rae_a = st.number_input("a (число)", value=7, step=1, key="util_rae_a_input")
    with col2:
        rae_m = st.number_input("m (модуль)", value=660, step=1, key="util_rae_m_input")
    if st.button("Найти обратный элемент", key="util_rae"):
        ui_mod_inverse(int(rae_a), int(rae_m), f"{rae_a}^{{-1}} \\bmod {rae_m}")

    st.divider()
    st.subheader("Быстрое возведение в степень")
    col1, col2, col3 = st.columns(3)
    with col1:
        fp_base = st.number_input("Основание", value=18, step=1, key="util_fp_base_input")
    with col2:
        fp_exp = st.number_input("Показатель", value=7, step=1, key="util_fp_exp_input")
    with col3:
        fp_mod = st.number_input("Модуль", value=713, step=1, key="util_fp_mod_input")
    if st.button("Вычислить", key="util_fp"):
        ui_fast_pow(int(fp_base), int(fp_exp), int(fp_mod))


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def solve_full_variant(
    alphabet: dict,
    *,
    rsa_p: int, rsa_q: int, rsa_e: int,
    plaintext: str, ciphertext: list,
    eg_p: int, eg_g: int, eg_y: int,
    sig_msg: str, p_hash: int, r_hash: int, k_sig: int,
    ver_msg: str, R_ver: int, S_ver: int,
) -> None:
    """Полное решение варианта в одном проходе."""
    st.markdown("## Задача 1. RSA — генерация ключей и шифрование")
    keys = solve_rsa_keygen(rsa_p, rsa_q, rsa_e)
    if not keys:
        return
    n, _, d = keys
    st.markdown(f"### Шифрование слова «{plaintext.upper()}»")
    solve_rsa_encrypt(plaintext, rsa_e, n, alphabet)

    st.markdown("## Задача 2. RSA — расшифрование (КТО)")
    solve_rsa_decrypt_crt(ciphertext, d, rsa_p, rsa_q, n, alphabet)

    st.markdown("## Задача 3. ЭЦП Эль-Гамаль")
    st.markdown("### 1. Нахождение секретного ключа x")
    x_sig = solve_elgamal_find_x(eg_p, eg_g, eg_y)
    if x_sig is None:
        return
    st.markdown(f"### 2. Хэш сообщения «{sig_msg.upper()}»")
    codes = encode_message(sig_msg, alphabet)
    H = ui_hash(codes, sig_msg.upper(), r_hash, p_hash)
    st.markdown("### 3. Создание подписи (R, S)")
    solve_elgamal_sign(H, x_sig, k_sig, eg_p, eg_g)
    st.markdown(f"### 4. Верификация подписи для «{ver_msg.upper()}»")
    solve_elgamal_verify(
        ver_msg, R_ver, S_ver, eg_p, eg_g, eg_y, r_hash, p_hash, alphabet
    )


def tab_variant(alphabet: dict) -> None:
    st.header("📝 Вариант 1 — полное решение")
    st.markdown(
        "Параметры варианта из контрольной:\n"
        "- **RSA:** $p=31,\\ q=23,\\ e=7$, открытый текст **RAIN**, шифртекст $(128,333,333,168)$\n"
        "- **Эль-Гамаль:** $p=37,\\ g=2,\\ y=17$, хэш-параметры $p_{hash}=13,\\ r=5$, "
        "подпись сообщения **RAIN**, $k=11$\n"
        "- **Верификация:** сообщение **BOOK**, подпись $(R_{ver},S_{ver}) = (13, 25)$"
    )
    if st.button("🚀 Решить вариант целиком", type="primary", key="solve_v1"):
        solve_full_variant(
            alphabet,
            rsa_p=31, rsa_q=23, rsa_e=7,
            plaintext="RAIN", ciphertext=[128, 333, 333, 168],
            eg_p=37, eg_g=2, eg_y=17,
            sig_msg="RAIN", p_hash=13, r_hash=5, k_sig=11,
            ver_msg="BOOK", R_ver=13, S_ver=25,
        )


def main() -> None:
    init_state()
    st.title("Асимметричная криптография — решалка")

    with st.sidebar:
        st.header("⚙️ Алфавит")
        alphabet_str = st.text_area(
            "Кодировка (формат A=1, B=2, ...)",
            value=default_alphabet_str(),
            height=200,
            key="alphabet_input",
        )
        try:
            alphabet = build_alphabet(alphabet_str)
            st.success(f"Загружено символов: {len(alphabet)}")
            with st.expander("Просмотр"):
                st.write(alphabet)
        except Exception as ex:
            st.error(f"Ошибка: {ex}")
            alphabet = build_alphabet(default_alphabet_str())

    tab0, tab1, tab2, tab3 = st.tabs(
        ["📝 Вариант 1", "RSA", "Эль-Гамаль", "Утилиты"]
    )
    with tab0:
        tab_variant(alphabet)
    with tab1:
        tab_rsa(alphabet)
    with tab2:
        tab_elgamal(alphabet)
    with tab3:
        tab_utils(alphabet)


if __name__ == "__main__":
    main()
