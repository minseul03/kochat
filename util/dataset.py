"""
@author : Hyunwoong
@when : 5/9/2020
@homepage : https://github.com/gusdnd852
"""
import random
import pandas as pd
import torch
from torch.utils.data import DataLoader
from torch.utils.data.dataset import TensorDataset

from config import Config
from util.tokenizer import Tokenizer


class Dataset:
    tok = Tokenizer()
    conf = Config()

    def embed_train(self, data_path):
        dataset = pd.read_csv(data_path)
        label = dataset['intent']
        label = label.map(self.count_intent(label)).tolist()
        data = dataset['question']
        data = [self.tok.tokenize(i, train=True) for i in data]
        return {'data': data, 'label': label}

    def intent_train(self, emb, data_path):
        # 1. load data from csv files
        dataset = self.embed_train(data_path)
        data, label = dataset['data'], dataset['label']
        dataset = [zipped for zipped in zip(data, label)]

        # 2. split data to train / test
        random.shuffle(dataset)
        split_point = int(len(dataset) * self.conf.intent_ratio)
        train_dataset = dataset[:split_point]
        test_dataset = dataset[split_point:]

        # 3. embedding and pad sequencing
        train_embedded, test_embedded = [], []
        train_label, test_label = [], []
        for data, label in train_dataset:
            data = self.pad_sequencing(emb.embed(data))
            train_embedded.append(data.unsqueeze(0))
            train_label.append(torch.tensor(label).unsqueeze(0))

        for data, label in test_dataset:
            data = self.pad_sequencing(emb.embed(data))
            test_embedded.append(data.unsqueeze(0))
            test_label.append(torch.tensor(label).unsqueeze(0))

        train_dataset = torch.cat(train_embedded, dim=0)
        test_dataset = torch.cat(test_embedded, dim=0)
        train_label = torch.cat(train_label, dim=0)
        test_label = torch.cat(test_label, dim=0)

        # 4. make mini batch
        train_set = TensorDataset(train_dataset, train_label)
        train_set = DataLoader(train_set, batch_size=self.conf.batch_size, shuffle=True)
        test_set = TensorDataset(test_dataset, test_label)
        test_set = DataLoader(test_set, batch_size=self.conf.batch_size, shuffle=True)

        return train_set, test_set

    def siamese_train(self, emb, data_path):
        # 1. load data from csv files
        dataset = self.embed_train(data_path)
        data, label = dataset['data'], dataset['label']
        dataset = [zipped for zipped in zip(data, label)]

        # 2. split data to train / test
        random.shuffle(dataset)
        split_point = int(len(dataset) * self.conf.intent_ratio)
        train_dataset = dataset[:split_point]
        test_dataset = dataset[split_point:]

        # 3. make even num of dataset for pairwise dataset
        if len(train_dataset) % 2 != 0:
            del train_dataset[len(test_dataset) - 1]

        if len(test_dataset) % 2 != 0:
            del test_dataset[len(test_dataset) - 1]

        # 4. make positive & negative pairs
        data_cache = None
        train_pos_pair, train_neg_pair = [], []
        test_pos_pair, test_neg_pair = [], []
        for i, data in enumerate(train_dataset):
            if i != 0:
                if data_cache[1] == data[1]:
                    train_pos_pair.append((data_cache[0], data[0]))
                else:
                    train_neg_pair.append((data_cache[0], data[0]))
            data_cache = data

        for i, data in enumerate(test_dataset):
            if i != 0:
                if data_cache[1] == data[1]:
                    test_pos_pair.append((data_cache[0], data[0]))
                else:
                    test_neg_pair.append((data_cache[0], data[0]))
            data_cache = data

        # 5. embedding and pad sequencing
        train_embedded, test_embedded = [], []
        train_label, test_label = [], []
        for data in train_pos_pair:
            d1, d2 = data[0], data[1]
            d1 = self.pad_sequencing(emb.embed(d1)).unsqueeze(0)
            d2 = self.pad_sequencing(emb.embed(d2)).unsqueeze(0)
            train_embedded.append(torch.cat([d1, d2], dim=0).unsqueeze(0))
            train_label.append(torch.tensor(1).unsqueeze(0))  # pos's label => 1

        for data in train_neg_pair:
            d1, d2 = data[0], data[1]
            d1 = self.pad_sequencing(emb.embed(d1)).unsqueeze(0)
            d2 = self.pad_sequencing(emb.embed(d2)).unsqueeze(0)
            train_embedded.append(torch.cat([d1, d2], dim=0).unsqueeze(0))
            train_label.append(torch.tensor(0).unsqueeze(0))  # neg's label => 1

        for data in test_pos_pair:
            d1, d2 = data[0], data[1]
            d1 = self.pad_sequencing(emb.embed(d1)).unsqueeze(0)
            d2 = self.pad_sequencing(emb.embed(d2)).unsqueeze(0)
            test_embedded.append(torch.cat([d1, d2], dim=0).unsqueeze(0))
            test_label.append(torch.tensor(1).unsqueeze(0))  # pos's label => 1

        for data in test_neg_pair:
            d1, d2 = data[0], data[1]
            d1 = self.pad_sequencing(emb.embed(d1)).unsqueeze(0)
            d2 = self.pad_sequencing(emb.embed(d2)).unsqueeze(0)
            test_embedded.append(torch.cat([d1, d2], dim=0).unsqueeze(0))
            test_label.append(torch.tensor(0).unsqueeze(0))  # neg's label => 1

        train_dataset = torch.cat(train_embedded, dim=0)
        test_dataset = torch.cat(test_embedded, dim=0)
        train_label = torch.cat(train_label, dim=0)
        test_label = torch.cat(test_label, dim=0)

        # 4. make mini batch
        train_set = TensorDataset(train_dataset, train_label)
        train_set = DataLoader(train_set, batch_size=self.conf.batch_size, shuffle=True)
        test_set = TensorDataset(test_dataset, test_label)
        test_set = DataLoader(test_set, batch_size=self.conf.batch_size, shuffle=True)

        return train_set, test_set

    def count_intent(self, label):
        count, index = {}, -1
        for lb in label:
            if lb not in count:
                index += 1
            count[lb] = index
        return count

    def read_line(self, fp):
        all_line = []
        while True:
            line = fp.readline()
            if not line: break
            all_line.append(line.replace('\n', '').split(','))

        return all_line

    def pad_sequencing(self, sequence):
        if sequence.size()[0] > self.conf.max_len:
            sequence = sequence[:self.conf.max_len]
        else:
            pad = torch.zeros(self.conf.max_len, self.conf.vector_size)
            for i in range(sequence.size()[0]):
                pad[i] = sequence[i]
            sequence = pad

        return sequence