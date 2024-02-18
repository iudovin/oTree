from otree.api import *
import numpy as np
import random
import time
import math


doc = """
Your app description
"""

# CHANGE LOG
# Find01 Обновление цены 
# Find02 Проверять лимиты позиций у игрока
# Find03 Сохранять шаг изменения коэффициентов
# Find04 Исключить отрицательную позицию по деньгам
# Find05 Отключить кнопку покупки инсайда после изменения игры
# Find06 Добавить таймер для покупки инсайда
# Find07 автоматический выбор админа при необходимости
# Find08 не выводить параметр а при а=0

class C(BaseConstants):
    NAME_IN_URL = 'gamestop'
    PLAYERS_PER_GROUP = None                    
    NUM_ROUNDS = 6
    ROUNDS_PARAMS_CHANGE = 3
    INITIAL_TIME = 90                               # общее время игры
    TIME_GAME_CHANGES = 60                          # время изменения игры (поведения цены)
    PRICE_CHANGE_TIMEOUT = 3                        # частота изменения цены
    INITIAL_POS = [(1000, 20),(7000, -100)]         # начальные позиции игроков
    POS_LIMITS = [[-200, 100], [-200, 200]]         # лимиты по акциям
    DISCOUNT_COEFF = 2                              # насколько дисконтируется шаг
    PRICE_MU = 0                                    # средняя флуктуация цены
    PRICE_SIGMA = 0.07                              # дисперсия флуктуации цены
    INSIDE_INITIAL_PRICE = 100.0                    # начальная цена инсайда
    A_PARAM = 0                                     # тренд для цены акции
    INSIDES_BOUGHT_FOR_DISCOUNT = 3                 # после покупки скольких инсайдов их цена меняется


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    # ПАРАМЕТРЫ ГРУППЫ
    price = models.FloatField(initial=50)                
    priceLastUpd = models.IntegerField(initial=0)           
    s = models.FloatField(initial=0)
    f = models.FloatField(initial=0)
    startTS = models.FloatField(initial=0)                  # точное время начала игры
    currentTS = models.FloatField(initial=0)                # текущее точное время
    gameTime = models.IntegerField(initial=0)               # сколько идет игра (без учета пауз)
    accTime = models.IntegerField(initial=0)                # сколько идет игра (с учетом пауз)
    numHedgeFunds = models.IntegerField(initial=0)          # число игроков-фондов
    numSmallTraders = models.IntegerField(initial=0)        # число игроков-инвесторов
    gamePaused = models.BooleanField(initial=True)          # остановлена ли игра
    timeLeft = models.IntegerField(initial=C.INITIAL_TIME)  # сколько осталось времени
    priceHistory = models.LongStringField(initial="")       # история цен (для анализа)
    price_change = models.FloatField(initial=0.0)           # шаг роста/падения цены после изменения игры
    

class Player(BasePlayer):
    # ПАРАМЕТРЫ ИГРОКА
    cash = models.FloatField(initial=0)                             # сколько денег
    pos = models.IntegerField(initial=0)                            # сколько акций
    numInsides = models.IntegerField(initial=0)                     # сколько инсайдов
    isAdmin = models.BooleanField(initial=False)                    # является ли админом
    isHedgeFund = models.BooleanField()                             # является ли хедж-фондом 
    s = models.FloatField(initial=0)                                # параметр s
    f = models.FloatField(initial=0)                                # параметр f
    history = models.LongStringField(initial="")                    # история сделок (для отображения)
    insides = models.LongStringField(initial="")                    # история инсайдов (для отображения)
    insidePrice = models.FloatField(initial=C.INSIDE_INITIAL_PRICE) # цена инсайда
    discount_val = models.FloatField(initial=1.0)                   # параметр для шага изменения коэффициентов
    discount_ptr = models.IntegerField(initial=0)                   # параметр для шага изменения коэффициентов
    k = models.IntegerField(initial=1)                              # 1 + numInsides // 3
    f_step = models.FloatField(initial=0)                           # шаг изменения параметра f при покупке инсайда
    s_step = models.FloatField(initial=0)                           # шаг изменения параметра s при покупке инсайда



# PAGES
class WaitToStart(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        players = group.get_players()
        
        # Find07 автоматический выбор админа при необходимости
        adminExists = any([(p.participant.label == 'admin') for p in players])
        for player in players:
            if adminExists:
                player.isAdmin = (player.participant.label == 'admin')
            else:
                player.isAdmin = player.id_in_group == 1
            player.isHedgeFund = bool(player.id_in_group % 2) ^ bool(group.round_number % 2)
            player.cash, player.pos = C.INITIAL_POS[int(player.isHedgeFund)]
        group.numHedgeFunds = sum(1 if p.isHedgeFund and not p.isAdmin else 0 for p in players)
        group.numSmallTraders = sum(0 if p.isHedgeFund or p.isAdmin else 1 for p in players)



def find_step_for_coeff(N, pos=10):
    """Шаг изменения коэффициента"""
    return float(1/(pos * N))


def get_trend_msg(s, f, a=C.A_PARAM):
    if a + s > f:
        return 'Рынок будет расти'
    elif a + s < f:
        return 'Рынок будет падать'
    return 'Рынок не будет ни расти, ни падать'



class Info(Page):
    timeout_seconds = 30

    @staticmethod
    def is_displayed(player):
        return player.round_number > 1 and (player.round_number - 1) % C.ROUNDS_PARAMS_CHANGE == 0
        
    @staticmethod
    def vars_for_template(player):
        return dict(
            old_params = C.POS_LIMITS[0],
            new_params = C.POS_LIMITS[1]
        )
    

class Bid(Page):    
    print('START GAME')
    
    @staticmethod
    def vars_for_template(player):
        return dict(
            s_init_cash = C.INITIAL_POS[0][0],
            s_init_pos = C.INITIAL_POS[0][1],
            f_init_cash = C.INITIAL_POS[1][0],
            f_init_pos = C.INITIAL_POS[1][1]
        )
    
    @staticmethod
    def live_method(player, data):
        print('<<', round(time.time(), 2), data)
        
        if data['type'] == 'timer':
            if player.group.timeLeft <= 0:
                player.group.gamePaused = True
                return
            
            if player.group.startTS == 0:
                player.group.startTS = time.time()
            player.group.currentTS = time.time()
            player.group.gameTime = player.group.accTime + math.floor(player.group.currentTS - player.group.startTS)
            player.group.timeLeft = C.INITIAL_TIME - player.group.gameTime
            if player.group.gameTime and player.group.gameTime % C.PRICE_CHANGE_TIMEOUT == 0 and player.group.priceLastUpd + 1 < player.group.gameTime:
                
                # Find01 Обновление цены
                # p(t+1)=p(t)+p(t)*a+p(t)*z = p(t)(1 + a + N(...))
                # a - тренд, z - броуновская случайность (нормальное распределение с нулевым средним)

                if player.group.gameTime <= C.TIME_GAME_CHANGES:
                    player.group.price *= (1 + C.A_PARAM + np.random.normal(C.PRICE_MU, C.PRICE_SIGMA))
                    player.group.price_change = (C.A_PARAM + player.group.s - player.group.f) * player.group.price
                else:
                    #player.group.price_change = player.group.price_change or (C.A_PARAM + player.group.s - player.group.f) * player.group.price
                    player.group.price += np.random.normal(C.PRICE_MU, C.PRICE_SIGMA) * player.group.price + player.group.price_change
                
                
                player.group.priceLastUpd = player.group.gameTime
                player.group.priceHistory += f"{player.group.price:.2f} "
        
        if data['type'] == 'control':
            if data['command'] == 'start':
                player.group.gamePaused = False
                player.group.gameTime = player.group.accTime
                player.group.startTS = time.time()
            elif data['command'] == 'pause':
                player.group.gamePaused = True
                player.group.accTime = player.group.gameTime
                player.group.gameTime = 0
            elif data['command'] == 'start_next':
                return {p.id_in_group: {"finishGame": 1} for p in player.group.get_players()}
                
        
        if player.group.gamePaused:
            return
            
        if data['type'] == 'buy':
        
            # Find02 Проверять лимиты позиций у игрока
            # Find04 Исключить отрицательную позицию по деньгам
            
            qnt = min(data['quantity'], C.POS_LIMITS[(player.round_number - 1) // C.ROUNDS_PARAMS_CHANGE][1] - player.pos, math.floor(player.cash / player.group.price))
            
            if qnt:
                player.cash -= player.group.price * qnt
                player.pos += qnt
                player.history = f"<tr><td>{player.group.gameTime}</td><td>{player.group.price:.2f}</td><td>{qnt}</td></tr>\n" + player.history
        
        if data['type'] == 'sell':
        
            # Find02 Проверять лимиты позиций у игрока
            
            qnt = min(data['quantity'], player.pos - C.POS_LIMITS[(player.round_number - 1) // C.ROUNDS_PARAMS_CHANGE][0])
            
            if qnt:
                player.pos -= qnt
                player.cash += player.group.price * qnt
                player.history = f"<tr><td>{player.group.gameTime}</td><td>{player.group.price:.2f}</td><td>{-qnt}</td></tr>\n" + player.history
        
        if data['type'] == 'buyInside':
            if player.group.gameTime >= C.TIME_GAME_CHANGES:
                return
            qnt = min(data['quantity'], math.floor(player.cash / player.insidePrice))

            if qnt:
                player.cash -= player.insidePrice * qnt
                player.numInsides += qnt
                
                player.s = player.group.s
                player.f = player.group.f
                
                # Find03 Сохранять шаг изменения коэффициентов
                if player.isHedgeFund:
                    player.s_step = find_step_for_coeff(player.group.numHedgeFunds) * player.discount_val
                    player.s += player.s_step
                    player.group.s = player.s
                else:
                    player.f_step = find_step_for_coeff(player.group.numSmallTraders) * player.discount_val
                    player.f += player.f_step
                    player.group.f = player.f
                
                player.discount_ptr += 1
                if player.discount_ptr % C.INSIDES_BOUGHT_FOR_DISCOUNT == 0:
                    player.discount_val /= C.DISCOUNT_COEFF
                    player.insidePrice = C.INSIDE_INITIAL_PRICE * player.k * np.log(2*player.k+2)
                    player.k += 1
                
                coeff = C.A_PARAM + player.s - player.f
                
                # Find08 не выводить параметр а при а=0
                if C.A_PARAM == 0:
                    player.insides = f"""<tr>
                        <td>{player.group.gameTime}</td>
                        <td>s={player.s:.2f}, f={player.f:.2f}, {get_trend_msg(player.s, player.f)}</td>
                    </tr>""" + player.insides
                else:
                    player.insides = f"""<tr>
                        <td>{player.group.gameTime}</td>
                        <td>a={C.A_PARAM}, s={player.s:.2f}, f={player.f:.2f}, a+s-f={coeff:.2f}, {get_trend_msg(player.s, player.f)}</td>
                    </tr>""" + player.insides
        
        if player.group.price <= 0:
            player.group.timeLeft = 0
            player.group.price = 0
            player.group.gamePaused = True

        data_ret = {p.id_in_group: {
            "time": p.group.gameTime, 
            "timeLeft": p.group.timeLeft,
            "price": round(p.group.price, 2),
            "pos": p.pos, 
            "cash": round(p.cash, 2), 
            "numInsides": p.numInsides,
            "history": p.history,
            "insides": p.insides,
            "insidePrice": round(p.insidePrice, 2),
            # Find05 Отключить кнопку покупки инсайда после изменения игры
            "gameChanged": p.group.timeLeft < C.INITIAL_TIME - C.TIME_GAME_CHANGES,
            # Find06 Добавить таймер для покупки инсайда
            "timeToBuyInside": p.group.timeLeft - C.INITIAL_TIME + C.TIME_GAME_CHANGES + 1 if p.group.timeLeft >= C.INITIAL_TIME - C.TIME_GAME_CHANGES and p.group.timeLeft < C.INITIAL_TIME - C.TIME_GAME_CHANGES + 10 else ""
        } for p in player.group.get_players()}
        print('>>', round(time.time(), 2), data_ret)
        return data_ret


class ResultsWaitPage(WaitPage):
    @staticmethod
    def after_all_players_arrive(group: Group):
        group.price = round(group.price, 2)
        group.s = round(group.s, 2)
        group.f = round(group.f, 2)
        for player in group.get_players():
            player.payoff = max(0, player.cash + player.pos * group.price)



class Results(Page):
    timeout_seconds = 30
    
    @staticmethod
    def vars_for_template(player):
        if C.A_PARAM == 0:
            return {'a': ''}
        return {'a', f"<math><mrow><mi>a</mi><mo>=</mo><mn>{C.A_PARAM}</mn></mrow></math>"}


page_sequence = [Info, WaitToStart, Bid, ResultsWaitPage, Results]
