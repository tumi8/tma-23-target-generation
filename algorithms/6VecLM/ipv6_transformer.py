import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchsummary import summary
import math, copy, time
from torch.autograd import Variable
from gensim.models import word2vec
import matplotlib.pyplot as plt
import seaborn
seaborn.set_context(context="talk")

word2vec_model_path = 'models/ipv62vec.model'
data_path = "data/processed_data/word_data.txt"
model_path = "models/ipv6_transformer.model"
generation_path = "data/generation_data/candidates.txt"

encoder_input_length = 16
total_epoch = 10
temperature = 0.015

train_data_size = 100000
train_batch_size = 100
train_nbatch = int(train_data_size / train_batch_size)
eval_data_size = 1000
eval_batch_size = 100
eval_nbatch = int(eval_data_size / eval_batch_size)

stack_layers = 6

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class EncoderDecoder(nn.Module):
    """
    A standard Encoder-Decoder architecture. Base for this and many
    other models.
    """

    def __init__(self, encoder, decoder, src_embed, tgt_embed, generator):
        super(EncoderDecoder, self).__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.src_embed = src_embed
        self.tgt_embed = tgt_embed
        self.generator = generator

    def forward(self, src, tgt, src_mask, tgt_mask):
        "Take in and process masked src and target sequences."
        return self.decode(self.encode(src, src_mask), src_mask,
                           tgt, tgt_mask)

    def encode(self, src, src_mask):
        return self.encoder(self.src_embed(src), src_mask)

    def decode(self, memory, src_mask, tgt, tgt_mask):
        return self.decoder(self.tgt_embed(tgt), memory, src_mask, tgt_mask)


class Generator(nn.Module):
    "Define standard linear + softmax generation step."
    def __init__(self, d_model, vocab):
        super(Generator, self).__init__()
        # self.proj = nn.Linear(d_model, vocab)
        self.proj = nn.Linear(d_model, d_model)

    def forward(self, x):
        # return F.log_softmax(self.proj(x), dim=-1)
        return torch.sigmoid(self.proj(x))


def clones(module, N):
    "Produce N identical layers."
    return nn.ModuleList([copy.deepcopy(module) for _ in range(N)])


class Encoder(nn.Module):
    "Core encoder is a stack of N layers"

    def __init__(self, layer, N):
        super(Encoder, self).__init__()
        self.layers = clones(layer, N)
        self.norm = LayerNorm(layer.size)

    def forward(self, x, mask):
        "Pass the input (and mask) through each layer in turn."
        for layer in self.layers:
            x = layer(x, mask)
        return self.norm(x)


class LayerNorm(nn.Module):
    "Construct a layernorm module (See citation for details)."
    def __init__(self, features, eps=1e-6):
        super(LayerNorm, self).__init__()
        self.a_2 = nn.Parameter(torch.ones(features))
        self.b_2 = nn.Parameter(torch.zeros(features))
        self.eps = eps

    def forward(self, x):
        mean = x.mean(-1, keepdim=True)
        std = x.std(-1, keepdim=True)
        return self.a_2 * (x - mean) / (std + self.eps) + self.b_2


class SublayerConnection(nn.Module):
    """
    A residual connection followed by a layer norm.
    Note for code simplicity the norm is first as opposed to last.
    """
    def __init__(self, size, dropout):
        super(SublayerConnection, self).__init__()
        self.norm = LayerNorm(size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, sublayer):
        "Apply residual connection to any sublayer with the same size."
        return x + self.dropout(sublayer(self.norm(x)))


class EncoderLayer(nn.Module):
    "Encoder is made up of self-attn and feed forward (defined below)"
    def __init__(self, size, self_attn, feed_forward, dropout):
        super(EncoderLayer, self).__init__()
        self.self_attn = self_attn
        self.feed_forward = feed_forward
        self.sublayer = clones(SublayerConnection(size, dropout), 2)
        self.size = size

    def forward(self, x, mask):
        "Follow Figure 1 (left) for connections."
        x = self.sublayer[0](x, lambda x: self.self_attn(x, x, x, mask))
        return self.sublayer[1](x, self.feed_forward)


class Decoder(nn.Module):
    "Generic N layer decoder with masking."

    def __init__(self, layer, N):
        super(Decoder, self).__init__()
        self.layers = clones(layer, N)
        self.norm = LayerNorm(layer.size)

    def forward(self, x, memory, src_mask, tgt_mask):
        for layer in self.layers:
            x = layer(x, memory, src_mask, tgt_mask)
        return self.norm(x)


class DecoderLayer(nn.Module):
    "Decoder is made of self-attn, src-attn, and feed forward (defined below)"

    def __init__(self, size, self_attn, src_attn, feed_forward, dropout):
        super(DecoderLayer, self).__init__()
        self.size = size
        self.self_attn = self_attn
        self.src_attn = src_attn
        self.feed_forward = feed_forward
        self.sublayer = clones(SublayerConnection(size, dropout), 3)

    def forward(self, x, memory, src_mask, tgt_mask):
        "Follow Figure 1 (right) for connections."
        m = memory
        x = self.sublayer[0](x, lambda x: self.self_attn(x, x, x, tgt_mask))
        x = self.sublayer[1](x, lambda x: self.src_attn(x, m, m, src_mask))
        return self.sublayer[2](x, self.feed_forward)


def subsequent_mask(size):
    "Mask out subsequent positions."
    attn_shape = (1, size, size)
    subsequent_mask = np.triu(np.ones(attn_shape), k=1).astype('uint8')
    return torch.from_numpy(subsequent_mask) == 0


def attention(query, key, value, mask=None, dropout=None):
    "Compute 'Scaled Dot Product Attention'"
    d_k = query.size(-1)
    scores = torch.matmul(query, key.transpose(-2, -1)) \
             / math.sqrt(d_k)
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e9)
    p_attn = F.softmax(scores, dim = -1)
    if dropout is not None:
        p_attn = dropout(p_attn)
    return torch.matmul(p_attn, value), p_attn


class MultiHeadedAttention(nn.Module):
    def __init__(self, h, d_model, dropout=0.1):
        "Take in models size and number of heads."
        super(MultiHeadedAttention, self).__init__()
        assert d_model % h == 0
        # We assume d_v always equals d_k
        self.d_k = d_model // h
        self.h = h
        self.linears = clones(nn.Linear(d_model, d_model), 4)
        self.attn = None
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, query, key, value, mask=None):
        "Implements Figure 2"
        if mask is not None:
            # Same mask applied to all h heads.
            mask = mask.unsqueeze(1)
        nbatches = query.size(0)

        # 1) Do all the linear projections in batch from d_model => h x d_k
        query, key, value = \
            [l(x).view(nbatches, -1, self.h, self.d_k).transpose(1, 2)
             for l, x in zip(self.linears, (query, key, value))]

        # 2) Apply attention on all the projected vectors in batch.
        x, self.attn = attention(query, key, value, mask=mask,
                                 dropout=self.dropout)

        # 3) "Concat" using a view and apply a final linear.
        x = x.transpose(1, 2).contiguous() \
            .view(nbatches, -1, self.h * self.d_k)
        return self.linears[-1](x)


class PositionwiseFeedForward(nn.Module):
    "Implements FFN equation."
    def __init__(self, d_model, d_ff, dropout=0.1):
        super(PositionwiseFeedForward, self).__init__()
        self.w_1 = nn.Linear(d_model, d_ff)
        self.w_2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        return self.w_2(self.dropout(F.relu(self.w_1(x))))


class Embeddings(nn.Module):
    def __init__(self, d_model, vocab, weight):
        super(Embeddings, self).__init__()
        # self.lut = nn.Embedding(vocab, d_model)
        self.lut = nn.Embedding.from_pretrained(weight)
        self.lut.weight.requires_grad = False
        self.d_model = d_model

    def forward(self, x):
        return self.lut(x) * math.sqrt(self.d_model)


class PositionalEncoding(nn.Module):
    "Implement the PE function."

    def __init__(self, d_model, dropout, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        # Compute the positional encodings once in log space.
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) *
                             -(math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + Variable(self.pe[:, :x.size(1)],
                         requires_grad=False)
        return self.dropout(x)


def make_model(word2vec_model, N=6, d_model=100, d_ff=2048, h=10, dropout=0.1):
    "Helper: Construct a models from hyperparameters."
    vocab = list(word2vec_model.wv.vocab.keys())
    src_vocab = tgt_vocab = len(vocab) + 1
    weight = torch.zeros(src_vocab, d_model)
    for i in range(len(word2vec_model.wv.index2word)):
        try:
            index = word2id(word2vec_model.wv.index2word[i], word2vec_model)
        except:
            continue
        weight[index, :] = torch.from_numpy(word2vec_model.wv.get_vector(
            id2word(word2id(word2vec_model.wv.index2word[i], word2vec_model), word2vec_model)))
    c = copy.deepcopy
    attn = MultiHeadedAttention(h, d_model)
    ff = PositionwiseFeedForward(d_model, d_ff, dropout)
    position = PositionalEncoding(d_model, dropout)
    model = EncoderDecoder(
        Encoder(EncoderLayer(d_model, c(attn), c(ff), dropout), N),
        Decoder(DecoderLayer(d_model, c(attn), c(attn),
                             c(ff), dropout), N),
        nn.Sequential(Embeddings(d_model, src_vocab, weight), c(position)),
        nn.Sequential(Embeddings(d_model, tgt_vocab, weight), c(position)),
        Generator(d_model, tgt_vocab))
    # This was important from their code.
    # Initialize parameters with Glorot / fan_avg.
    for p in model.parameters():
        if p.dim() > 1:
            nn.init.xavier_uniform(p)
    return model


class Batch:
    "Object for holding a batch of data with mask during training."

    def __init__(self, src, trg=None, pad=0):
        self.src = src
        self.src_mask = (src != pad).unsqueeze(-2)
        if trg is not None:
            self.trg = trg[:, :-1]
            self.trg_y = trg[:, 1:]
            self.trg_mask = \
                self.make_std_mask(self.trg, pad)
            self.ntokens = (self.trg_y != pad).data.sum()

    @staticmethod
    def make_std_mask(tgt, pad):
        "Create a mask to hide padding and future words."
        tgt_mask = (tgt != pad).unsqueeze(-2)
        tgt_mask = tgt_mask & Variable(
            subsequent_mask(tgt.size(-1)).type_as(tgt_mask.data))
        return tgt_mask


def run_epoch(data_iter, model, loss_compute):
    "Standard Training and Logging Function"
    start = time.time()
    total_tokens = 0
    total_loss = 0
    tokens = 0
    for i, batch in enumerate(data_iter):
        # to device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        batch.src = batch.src.to(device)
        batch.trg = batch.trg.to(device)
        batch.src_mask = batch.src_mask.to(device)
        batch.trg_mask = batch.trg_mask.to(device)
        batch.trg_y = batch.trg_y.to(device)

        out = model.forward(batch.src, batch.trg,
                            batch.src_mask, batch.trg_mask) # model(batch.src, batch.trg, batch.src_mask, batch.trg_mask)
        loss = loss_compute(out, batch.trg_y, batch.ntokens)
        total_loss += loss
        total_tokens += batch.ntokens
        tokens += batch.ntokens
        if i % 50 == 1:
            elapsed = time.time() - start
            print("Epoch Step: %d Loss: %f Tokens per Sec: %f" %
                    (i, loss / batch.ntokens, tokens / elapsed))
            start = time.time()
            tokens = 0
    return total_loss / total_tokens


global max_src_in_batch, max_tgt_in_batch
def batch_size_fn(new, count, sofar):
    "Keep augmenting batch and calculate total number of tokens + padding."
    global max_src_in_batch, max_tgt_in_batch
    if count == 1:
        max_src_in_batch = 0
        max_tgt_in_batch = 0
    max_src_in_batch = max(max_src_in_batch,  len(new.src))
    max_tgt_in_batch = max(max_tgt_in_batch,  len(new.trg) + 2)
    src_elements = count * max_src_in_batch
    tgt_elements = count * max_tgt_in_batch
    return max(src_elements, tgt_elements)


class NoamOpt:
    "Optim wrapper that implements rate."

    def __init__(self, model_size, factor, warmup, optimizer):
        self.optimizer = optimizer
        self._step = 0
        self.warmup = warmup
        self.factor = factor
        self.model_size = model_size
        self._rate = 0

    def step(self):
        "Update parameters and rate"
        self._step += 1
        rate = self.rate()
        for p in self.optimizer.param_groups:
            p['lr'] = rate
        self._rate = rate
        self.optimizer.step()

    def rate(self, step=None):
        "Implement `lrate` above"
        if step is None:
            step = self._step
        return self.factor * \
               (self.model_size ** (-0.5) *
                min(step ** (-0.5), step * self.warmup ** (-1.5)))


def get_std_opt(model):
    return NoamOpt(model.src_embed[0].d_model, 2, 4000,
                   torch.optim.Adam(model.parameters(), lr=0, betas=(0.9, 0.98), eps=1e-9))


class LabelSmoothing(nn.Module):
    "Implement label smoothing."

    def __init__(self, size, padding_idx, word2vec_model, smoothing=0.0):
        super(LabelSmoothing, self).__init__()
        # self.criterion = nn.KLDivLoss(size_average=False)
        self.criterion = nn.CosineEmbeddingLoss()
        self.word2vec_model = word2vec_model
        self.padding_idx = padding_idx
        self.confidence = 1.0 - smoothing
        self.smoothing = smoothing
        self.size = size
        self.true_dist = None

    def forward(self, x, target):
        assert x.size(1) == self.size
        true_dict = [self.word2vec_model.wv[id2word(int(id.cpu().numpy()), self.word2vec_model)] for id in target]
        # print(x.shape)
        # print(x)
        # print(Variable(torch.Tensor(true_dict), requires_grad=False).shape)
        # print(Variable(torch.Tensor(true_dict), requires_grad=False))
        # return self.criterion(x, Variable(torch.Tensor(true_dict), requires_grad=False), torch.ones(self.size, 1))
        loss = self.criterion(x.to(device), Variable(torch.Tensor(true_dict).to(device), requires_grad=False), torch.ones(x.shape[0]).to(device))
        return loss
    # def forward(self, x, target):
    #     assert x.size(1) == self.size
    #     true_dist = x.data.clone()
    #     true_dist.fill_(self.smoothing / (self.size - 2))
    #     true_dist.scatter_(1, target.data.unsqueeze(1), self.confidence)
    #     true_dist[:, self.padding_idx] = 0
    #     mask = torch.nonzero(target.data == self.padding_idx)
    #     if mask.dim() > 0:
    #         true_dist.index_fill_(0, mask.squeeze(), 0.0)
    #     self.true_dist = true_dist
    #     return self.criterion(x, Variable(true_dist, requires_grad=False))


def word2id(word, word2vec_model):
    vocab = list(word2vec_model.wv.vocab.keys())
    word2id_dict = {word: i+1 for i, word in enumerate(vocab)}
    return word2id_dict[word]


def id2word(id, word2vec_model):
    vocab = list(word2vec_model.wv.vocab.keys())
    id2word_dict = {i+1: word for i, word in enumerate(vocab)}
    return id2word_dict[id]


def data_gen(data, batch, nbatches):
    "Generate random data for a src-tgt copy task."
    for i in range(nbatches):
        # data = torch.from_numpy(np.random.randint(1, V, size=(batch, 10)))
        # data[:, 0] = 1
        # src = Variable(data, requires_grad=False)
        # tgt = Variable(data, requires_grad=False)
        src = torch.from_numpy(data[i * batch: (i + 1) * batch, :encoder_input_length])
        tgt = torch.from_numpy(data[i * batch: (i + 1) * batch, encoder_input_length:])
        yield Batch(src, tgt, 0)


class SimpleLossCompute:
    "A simple loss compute and train function."

    def __init__(self, generator, criterion, opt=None):
        self.generator = generator
        self.criterion = criterion
        self.opt = opt

    def __call__(self, x, y, norm):
        x = self.generator(x)
        loss = self.criterion(x.contiguous().view(-1, x.size(-1)),
                              y.contiguous().view(-1)) / norm
        loss.backward()
        if self.opt is not None:
            self.opt.step()
            self.opt.optimizer.zero_grad()
        return loss.item() * norm


def sample(preds, temperature):
    preds = np.asarray(preds).astype("float64")
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds)
    probas = np.random.multinomial(1, preds, 1)
    return np.argmax(probas)


def next_generation(word2vec_model, vector, temperature, index):
    vocab = word2vec_model.wv.vocab.keys()
    attribute_index = str(chr(index + 87))
    attribute_values = [str(hex(i))[-1] for i in range(16)]
    index_words = []
    for attribute_value in attribute_values:
        if attribute_value + attribute_index in vocab:
            index_words.append(attribute_value + attribute_index)
    index_word_vectors = [[word2vec_model.wv[index_word]] for index_word in index_words]
    similarity = [torch.cosine_similarity(torch.Tensor(index_word_vectors[i]).to(device), vector) for i in range(len(index_words))]
    preds = F.softmax(torch.Tensor(similarity), dim=0)
    return word2id(index_words[sample(preds, temperature)], word2vec_model)


def greedy_decode(model, word2vec_model, src, src_mask, max_len, start_symbol):
    model, src, src_mask = model.to(device), src.to(device), src_mask.to(device)
    memory = model.encode(src, src_mask)
    ys = torch.ones(1, 1).fill_(start_symbol).type_as(src.data)
    ys = ys.to(device)

    for i in range(max_len-1):
        out = model.decode(memory, src_mask,
                           Variable(ys),
                           Variable(subsequent_mask(ys.size(1))
                                    .type_as(src.data)))
        # prob = models.generator(out[:, -1])
        # _, next_word = torch.max(prob, dim=1)
        vector = model.generator(out[:, -1])
        next_word = next_generation(word2vec_model, vector, temperature, i + 17)
        # next_word = next_word.data[0]
        ys = torch.cat([ys,
                        torch.ones(1, 1).type_as(src.data).fill_(next_word)], dim=1)
    return ys


def write_data(target_generation):
    f = open(generation_path, "a+")
    for address in target_generation:
        f.write(address + "\n")
    f.close()


if __name__ == "__main__":

    # Train the simple copy task.
    # V = 17
    # criterion = LabelSmoothing(size=475, padding_idx=0, smoothing=0.0)
    word2vec_model = word2vec.Word2Vec.load(word2vec_model_path)

    f = open(data_path, "r")
    train_data = [[word2id(nybble, word2vec_model) for nybble in address[:-1].split()]
                  for address in f.readlines()[:train_data_size]]
    train_data = np.array(train_data)
    f.close()
    f = open(data_path, "r")
    eval_data = [[word2id(nybble, word2vec_model) for nybble in address[:-1].split()]
                 for address in f.readlines()[-eval_data_size:]]
    eval_data = np.array(eval_data)
    f.close()

    criterion = LabelSmoothing(size=100, padding_idx=0, word2vec_model=word2vec_model, smoothing=0.0)
    model = make_model(word2vec_model, N=stack_layers)
    model_opt = NoamOpt(model.src_embed[0].d_model, 1, 400,
            torch.optim.Adam(model.parameters(), lr=0, betas=(0.9, 0.98), eps=1e-9))

    # to device
    model = model.to(device)
    criterion = criterion.to(device)

    for epoch in range(total_epoch):
        print("Total Epoch: ", epoch + 1)
        model.train()
        run_epoch(data_gen(train_data, train_batch_size, train_nbatch), model,
                  SimpleLossCompute(model.generator, criterion, model_opt))
        model.eval()
        print("Eval:")
        print(run_epoch(data_gen(eval_data, eval_batch_size, eval_nbatch), model,
                        SimpleLossCompute(model.generator, criterion, None)))
    torch.save(model, model_path)

    model.eval()
    # src = Variable(torch.LongTensor([[1,2,3,4,5,6,7,8,9,10]]))
    # src_mask = Variable(torch.ones(1, 1, 10))
    # print(greedy_decode(models, src, src_mask, max_len=10, start_symbol=1))

    f = open(data_path, "r")
    data = np.array([[word2id(nybble, word2vec_model) for nybble in address[:-1].split()]
                     for address in f.readlines()[:train_data_size]])
    test_data = np.array(data[:, :encoder_input_length])
    start_symbols = np.array(data[:, encoder_input_length])
    f.close()

    target_generation = []
    for i in range(len(test_data)):
        src = Variable(torch.LongTensor([test_data[i]]))
        src_mask = Variable(torch.ones(1, 1, encoder_input_length))
        predict = greedy_decode(model, word2vec_model, src, src_mask,
                                max_len=32-encoder_input_length, start_symbol=start_symbols[i])
        predict = np.append(np.array(test_data[i]), predict.cpu().numpy())
        predict_words = [id2word(i, word2vec_model) for i in predict]
        # predict_words_str = " ".join(predict_words)
        # print(predict_words_str)
        predict_address = [word[0] for word in predict_words]
        count = 0
        predict_address_str = ""
        for i in predict_address:
            predict_address_str += i
            count += 1
            if count % 4 == 0 and count != 32:
                predict_address_str += ":"
        print(predict_address_str)
        target_generation.append(predict_address_str)
    target_generation = list(set(target_generation))
    write_data(target_generation)

