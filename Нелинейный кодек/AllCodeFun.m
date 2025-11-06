function R = AllCodeFun(args, COEFF, FunType)
%% АЛГОРИТМ ВЫЧИСЛЕНИЯ ВСЕЙ СИСТЕМЫ КОДИРУЮЩИХ ДЛЯ ПАРЫ АРГУМЕНТОВ xy
% xy — вектор двух значений типа fi
% args(1) ——> x = h(k - 1)
% args(2) ——> y = h(k - 2)
% COEFF — матрица коэффициентов в системе уравнений, кодирующих процесс x
% FunType — тип функции:
%   1: p1*x + p2*y + p3
%   2: p1*x^2 + p2*y + p3
%   3: p1*x^2 + p2*y^2 + p3
%   4: p1*x^3 + p2*y^2 + p3
%   5: p1*x + p2*x*y + p3*y + p4
%
% A <—— не используется!
% A = fi(1, 1, M, 0, F) — опорная/эталонная единица в системе
% дискретной математики, где M — разрядность счёта: 4, 8, 12, 16 и т.п.;
% F — формат вычислений с фиксированной точкой:
% F = fimath('ProductWordLength', M, ...
%    'ProductFractionLength', 0, ...
%    'SumWordLength', M, ...
%    'SumFractionLength', 0, ...
%    'ProductMode', 'SpecifyPrecision', ...
%    'SumMode', 'SpecifyPrecision', ...
%    'OverflowAction', 'Wrap');
%

% ПРИМЕР задания функции
% args = cast([97 -112], 'like', A)
% COEFF = cast( ...
%   [59   -70   -72
%   -31    55   -31
%   103  -103   104
%   -79    55   -97
%    99   -67  -117
%   -62   -23    48
%   -23   -54   -52
%  -128   -90   127
%    11   -49   -81
%   -40    34    14
%    37  -123    23
%   110    31    -1
%    22   -77   -10
%   -62   -27   -89
%   102    -9   -62
%  -124    76    56], ...
% 'like', A);
% FunType = 1;

% ВАЖНО:
% 1) Количество строк в COEFF должно быть равным объёму алфавита
% передаваемой информации: N = 2^Q, где Q принадлежит отрезку [1; M].
% 2) Количество столбцов в COEFF должно быть равным количеству параметров
%    в системе из 2^Q функций типа FunType.
% 3) Сами коэффициенты COEFF удобно подбирать, используя функцию
%    COEFF = FindCoef4NDF(InData, A, M, Q, FunType, tol).
% 4) Количество переменных в args должно совпадать с количеством переменных,
%    заданных в системе кодирующих функций типа FunType.
%    Для всех применяемых в настоящее время функций — их два.
% 5) Все расчёты в алгоритме ведутся в рамках целочисленной математики
%    GF(2^M).




N = size(COEFF, 1);
R = zeros(N, 1, 'like', COEFF(1, 1));
switch FunType
    case 1  % a*x + b*y + q
        for k = 1:N
            R(k) = COEFF(k, 1)*args(1) + COEFF(k, 2)*args(2) + COEFF(k, 3);
        end
    case 2  % a*x^2 + b*y + q
        for k = 1:N
            R(k) = COEFF(k, 1)*args(1)^2 + COEFF(k, 2)*args(2) + COEFF(k, 3);
        end
    case 3  % a*x^2 + b*y^2 + q
        for k = 1:N
            R(k) = COEFF(k, 1)*args(1)^2 + COEFF(k, 2)*args(2)^2 + COEFF(k, 3);
        end
    case 4  % a*x^3 + b*y^2 + q
        for k = 1:N
            R(k) = COEFF(k, 1)*args(1)^3 + COEFF(k, 2)*args(2)^2 + COEFF(k, 3);
        end
    case 5  % a*x + b*x*y + c*y + q
        for k = 1:N
            R(k) = COEFF(k, 1)*args(1) + COEFF(k, 2)*args(1)*args(2) + ...
                COEFF(k, 3)*args(2) + COEFF(k, 4);
        end
    otherwise
        disp('Неизвестный тип функции')
        R = cast(0, 'like', COEFF(1, 1));
        return
end

