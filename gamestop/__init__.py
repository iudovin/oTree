from otree.api import *
import numpy as np
import random
import time
import math


doc = """
Your app description
"""

# Find01 Обновление цены 
# Find02 Проверять лимиты позиций у игрока
# Find03 Сохранять шаг изменения коэффициентов

class C(BaseConstants):
    NAME_IN_URL = 'gamestop'
    PLAYERS_PER_GROUP = None                    
    NUM_ROUNDS = 3                              
    INITIAL_TIME = 120                          # общее время игры
    TIME_GAME_CHANGES = 60                      # время изменения игры (поведения цены)
    PRICE_CHANGE_TIMEOUT = 3                    # частота изменения цены
    INITIAL_POS = [(1000, 5000),(1000, -10000)] # начальные позиции игроков
    POS_LIMITS = [-15000, 7000]                 # лимиты по акциям
    DISCOUNT_COEFF = 2                          # насколько дисконтируется шаг
    PRICE_ALPHA = 1.02                          # рост цены до изменения игры
    PRICE_MU = 0                                # средняя флуктуация цены
    PRICE_SIGMA = 0.03                          # дисперсия флуктуации цены
    INSIDE_INITIAL_PRICE = 100.0                # начальная цена инсайда
    A_PARAM = 0.2                               # параметр a для цены после изменения игры
    INSIDES_BOUGHT_FOR_DISCOUNT = 3             # после покупки скольких инсайдов их цена меняется


class Subsession(BaseSubsession):
    pass


class Group(BaseGroup):
    # ПАРАМЕТРЫ ГРУППЫ
    price = models.FloatField(initial=100.0)                
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
        #group.price = 100
        #group.s = 0 #np.random.uniform(0, 1)
        #group.f = 0 #np.random.uniform(0, 1)
        for player in players:
            #player.isAdmin = (player.participant.label == 'admin')
            player.isAdmin = player.id_in_group == 1
            player.isHedgeFund = bool(player.id_in_group % 2) ^ bool(group.round_number % 2)
            player.cash, player.pos = C.INITIAL_POS[int(player.isHedgeFund)]
        group.numHedgeFunds = sum(1 if p.isHedgeFund and not p.isAdmin else 0 for p in players)
        group.numSmallTraders = sum(0 if p.isHedgeFund or p.isAdmin else 1 for p in players)
        





'''
def price_change(t_now, t_before, p_before, t_change, price_zero=100, a=0.2, sigma_squared=150, mu=0, s=0, f=0):
    if t_now != t_before and t_now != 0: 
        if t_now < t_change:
            return price_zero + a * t_now + np.random.normal(mu, np.sqrt(sigma_squared))
        else:
            return price_zero + a * t_now + s * (t_now - t_change) - f * (t_now - t_change) + np.random.normal(mu, np.sqrt(sigma_squared)) 
    else:
        return p_before
'''

def find_step_for_coeff(N, pos=10):
    """Шаг изменения коэффициента"""
    return float(1/(pos * N))


def get_trend_msg(s, f, a=0.2):
    if a + s > f:
        return 'Рынок будет расти'
    elif a + s < f:
        return 'Рынок будет падать'
    return 'Рынок не будет ни расти, ни падать'



# ToDo ограничить абсолютную позицию игрока: [-15000, 5000]

class Bid(Page):
    #timeout_seconds = 60
    
    print('START GAME')
    
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
                # p(t+1)=p(t)+p(t)*a+p(t)*z
                # a - тренд, z - броуновская случайность (нормальное распределение с нулевым средним)
                #new_price = player.group.price * (1.02 + np.random.normal(0, np.sqrt(150)))
                if player.group.gameTime < C.TIME_GAME_CHANGES:
                    player.group.price *= (C.PRICE_ALPHA + np.random.normal(C.PRICE_MU, C.PRICE_SIGMA))
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
            
            #qnt = min(data['quantity'], math.floor(player.cash / player.group.price))
            #qnt = data['quantity']
            qnt = min(data['quantity'], C.POS_LIMITS[1] - player.pos, math.floor(player.cash / player.group.price))
            
            if qnt:
                player.cash -= player.group.price * qnt
                player.pos += qnt
                player.history = f"<tr><td>{player.group.gameTime}</td><td>{player.group.price:.2f}</td><td>{qnt}</td></tr>\n" + player.history
        
        if data['type'] == 'sell':
        
            # Find02 Проверять лимиты позиций у игрока
            
            #qnt = min(player.pos, data['quantity'])
            #qnt = data['quantity']
            qnt = min(data['quantity'], player.pos - C.POS_LIMITS[0])
            
            if qnt:
                player.pos -= qnt
                player.cash += player.group.price * qnt
                player.history = f"<tr><td>{player.group.gameTime}</td><td>{player.group.price:.2f}</td><td>{-qnt}</td></tr>\n" + player.history
        
        if data['type'] == 'buyInside':
            if player.group.gameTime >= C.TIME_GAME_CHANGES:
                return
            qnt = min(data['quantity'], math.floor(player.cash / player.insidePrice))
            #qnt = data['quantity']
            if qnt:
                player.cash -= player.insidePrice * qnt
                player.numInsides += qnt
                
                player.s = player.group.s
                player.f = player.group.f
                
                # Find03 Сохранять шаг изменения коэффициентов
                if player.isHedgeFund:
                    player.s_step = find_step_for_coeff(player.group.numSmallTraders) * player.discount_val
                    player.s += player.s_step
                    player.group.s = player.s
                else:
                    player.f_step = find_step_for_coeff(player.group.numHedgeFunds) * player.discount_val
                    player.f += player.f_step
                    player.group.f = player.f
                
                player.discount_ptr += 1
                if player.discount_ptr % C.INSIDES_BOUGHT_FOR_DISCOUNT == 0:
                    player.discount_val /= C.DISCOUNT_COEFF
                    player.insidePrice = C.INSIDE_INITIAL_PRICE * player.k * np.log(2*player.k+2)
                    player.k += 1
                
                coeff = C.A_PARAM + player.s - player.f
                player.insides = f"""<tr>
                    <td>{player.group.gameTime}</td>
                    <td>a=0.2, s={player.s:.2f}, f={player.f:.2f}, a+s-f={coeff:.2f}, {get_trend_msg(player.s, player.f)}</td>
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
            "insidePrice": round(p.insidePrice, 2)
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


page_sequence = [WaitToStart, Bid, ResultsWaitPage, Results]
