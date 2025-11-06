function y = BitChange(x, pos)
%% Меняем бит в позиции pos на противоположное значение
%y = x;
if bitget(x, pos), y = bitset(x, pos, 0);
else
    y = bitset(x, pos, 1);
end
