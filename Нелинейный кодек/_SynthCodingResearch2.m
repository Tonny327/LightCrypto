%% ЗАЧИСТКА и ИНИЦИАЛИЗАЦИЯ
clear, clc, close all hidden
% Загружаем информацию об НПФ из файла
LoadDataFromFile = 0;
% Работаем вообще без внесения ошибок (тестовые цели)
% 0 — работаем без внесения ошибок
% 1 — ошибки в поток вносятся
ErrGlobal = 1;


%% Здесь представлена реализация кодека со вставками синтетических блоков
% на основе проверки гипотез о наличии/отсутствии ошибки и её местоположении.



%% ИСХОДНЫЕ ДАННЫЕ
% Разрядность процессора, бит
M = 8;
% Длина информационного блока, бит
Q = 6;
% Количество определённых функций
N = 2^Q;
% Тип порождающей функции
FunType = 1;
% Длительность наблюдения, количество блоков СКК.
% Всего отсчётов, для кода «1 – 1», 2*L.
L = 100;
% Допускается ли ситуация отсутствия ошибки в блоке:
% noErr = 0 — одна ошибка есть всегда;
% noErr = 1 — возможно отсутствие ошибки;
noErr = 1;


% Формат вычислений с фиксированной точкой
F = fimath('ProductWordLength', M, ...
    'ProductFractionLength', 0, ...
    'SumWordLength', M, ...
    'SumFractionLength', 0, ...
    'ProductMode', 'SpecifyPrecision', ...
    'SumMode', 'SpecifyPrecision', ...
    'OverflowAction', 'Wrap');
% Эталонное значение
A = fi(1, 1, M, 0, F);  % со знаком; разрядность M

if ~LoadDataFromFile
    % Матрица коэффициентов порождающих функций
    AA = cast(randi([-2^(M - 1), 2^(M - 1) - 1], N, 1), 'like', A);
    BB = cast(randi([-2^(M - 1), 2^(M - 1) - 1], N, 1), 'like', A);
    QQ = cast(randi([-2^(M - 1), 2^(M - 1) - 1], N, 1), 'like', A);
    if FunType >= 1 && FunType <= 4
        COEFF = [AA BB QQ];
    else
        CC = cast(randi([-2^(M - 1), 2^(M - 1) - 1], N, 1), 'like', A);
        COEFF = [AA BB CC QQ];
    end
else
    FN = 'SynthCodingResearch2_data.txt';
    NFF = ReadNimData(FN);
    COEFF = NFF{4};
end

% Информационный поток
INF = [0; randi(2^Q, L - 1, 1)];

% Начальные условия и вектор сигнала
h1 = fi(3, 1, M, 0, F);
v1 = fi(-2, 1, M, 0, F);
sig = zeros(2*L, 1, 'like', A);



%% К О Д И Р О В А Н И Е
sig(1) = h1; sig(2) = v1;
% Справочно:
% предыдущий блок: h(k - 1) = sig(2*BL - 3);  v(k - 1) = sig(2*BL - 2)
% текущий блок:    h(k) = sig(2*BL - 1);  v(k) = sig(2*BL)
% k — номер такта; два такта – один блок
for BL = 2:L
    II = INF(BL);
    % сигнальный отсчёт
    x = sig(2*BL - 2); y = sig(2*BL - 3);
    RR = AllCodeFun([x y], COEFF, FunType);
    sig(2*BL - 1) = RR(II);
    % проверочный синтетический отсчёт
    x = sig(2*BL - 1); y = sig(2*BL - 2);
    RR = AllCodeFun([x y], COEFF, FunType);
    sig(2*BL) = RR(II);
end



%% ПОМЕХА
% Аддитивный гауссов шум не годится, поскольку не отражает
% реальный канал связи в основной полосе частот. Предполагаем,
% что в отсчётных значениях сигнала на произвольных позициях возникают
% ОДИНОЧНЫЕ ошибки. Помеху реализуем циклом, который в каждом блоке
% искажает 1 бит в случайной позиции отсчёта в двоичном представлении.
% При noErr = 1 ошибка может отсутствовать.
r = sig;

if ErrGlobal
    % Вектор вносимых ошибок:
    % 0 — ошибка не вносится; 1 — ошибка будет в блоке H; 2 — в блоке V
    if noErr, errPosVec = [0; randi([0 2], L - 1, 1)];
    else, errPosVec = [0; randi([1 2], L - 1, 1)];
    end
    for BL = 2:L
        errPos = randi(Q);  % случайное значение от 1 до Q
        switch errPosVec(BL)
            % ошибка вносится в субблок h
            case 1, r(2*BL - 1) = BitChange(r(2*BL - 1), errPos);
            % ошибка вносится в субблок v
            case 2, r(2*BL) = BitChange(r(2*BL), errPos);
            % ошибка не вносится; случай, когда noErr = 1
            otherwise
        end
    end
else
    errPosVec = zeros(L, 1);
end
% Для декодера:
rr = r;  % rr исправляется при декодировании; r – для графиков


%% Д Е К О Д И Р О В А Н И Е
INF_ = zeros(L, 1);
for BL = 2:L
    errPosDec = 0;

    % 1. Проверка гипотезы «ОШИБКА ОТСУТСТВУЕТ»
    [I_, ePos] = Decode11ext(rr(2*BL - 2), rr(2*BL - 3), ...
        rr(2*BL - 1), rr(2*BL), COEFF, FunType, 0);
    if isempty(I_)
        errPosDec = 1;  % переход к гипотезе «ошибка в H»
        % disp('В декодируемом блоке есть ОШИБКА!')
    else
        INF_(BL) = I_(1);
        %disp('Декодированное значение при отсутствии ошибок:  ')
    end

    % 2. Проверка гипотезы «ОШИБКА в СУББЛОКЕ H»:
    if errPosDec == 1
        [I_, ePos] = Decode11ext(rr(2*BL - 2), rr(2*BL - 3), ...
            rr(2*BL - 1), rr(2*BL), COEFF, FunType, 1);
        if isempty(I_)
            errPosDec = 2;  % переход к гипотезе «ошибка в V»
            % disp('Проверен субблок H. Нет, ошибка в субблоке V!')
        else
            INF_(BL) = I_(1);
        end
    end

    % 3. Проверка гипотезы «ОШИБКА в СУББЛОКЕ V»:
    if errPosDec == 2
        [I_, ePos] = Decode11ext(rr(2*BL - 2), rr(2*BL - 3), ...
             rr(2*BL - 1), rr(2*BL), COEFF, FunType, 2);
        % Здесь чего-то не хватает. Нужно продумать и доработать.
        if ~isempty(I_)
            INF_(BL) = I_(1);
        end
    end

    % ИСПРАВЛЕНИЕ ОШИБКИ в СИГНАЛЕ r
    % исправление в h:
    if errPosDec == 1
        rr(2*BL - 1) = BitChange(rr(2*BL - 1), ePos);
    end
    % исправление в v:
    if errPosDec == 2 && isscalar(ePos)
        rr(2*BL) = BitChange(rr(2*BL), ePos);
    end
end



%% ОЦЕНКА КАЧЕСТВА ДЕКОДИРОВАНИЯ
nErr = nnz(INF ~= INF_);
tt = find(INF ~= INF_);
disp('Количество ошибок:'), disp(nErr)
disp('На позициях:'), disp(tt)











