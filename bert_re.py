import torch.nn as nn
import exp_models
import base_models
from transformers import BertConfig
from Dataset import Wikitext
from accelerate import Accelerator
from torch.utils.tensorboard import SummaryWriter
from transformers import BertConfig, get_cosine_schedule_with_warmup
import torch.optim as optim
from base_loggers import l_train_loss, l_test_loss, l_ntk

import torch
import numpy as np
import random

from io import FileIO

class bert_test(exp_models.exp_models):
    _accelerator: Accelerator
    _l_train_loss: l_train_loss
    _l_test_loss: l_test_loss
    _l_ntk: l_ntk
    _writer: SummaryWriter
    _ntk_writer: FileIO
    _num_epochs: int

    def __init__(self, model_name: str, config_file: str):
        config = BertConfig.from_json_file(config_file)
        
        self._base_model  = base_models.BertForMLM(config=config)
        self._dataset     = Wikitext(config=config)
        self._writer      = SummaryWriter("log/" + model_name)
        self._ntk_writer  = open("log/" + model_name + "_lmax.log", "wb+")
        
        self._train_loader = self._dataset.train_loader
        self._val_loader   = self._dataset.val_loader
        self._test_loader  = self._dataset.test_loader
        
        self._l_train_loss = l_train_loss(self._base_model, self._writer)
        self._l_test_loss  = l_test_loss(self._base_model, self._writer)
        self._l_ntk        = l_ntk(self._base_model, self._ntk_writer)
        
        
    
    def init_model(self) -> None:
        
        self._num_epochs = 80
        num_updates = self._num_epochs * len(self._train_loader)

        self._optimizer = optim.AdamW(self._base_model.parameters(), lr=2e-4, weight_decay=0)
        self._lr_scheduler = get_cosine_schedule_with_warmup(
            optimizer=self._optimizer,
            num_warmup_steps=num_updates * 0.05,
            num_training_steps=num_updates,
        )

    
    def train(self) -> None:
        for epoch in range(self._num_epochs):
            self._l_ntk.compute(train_loader=self._train_loader)

            self._base_model.train()
            for i, batch in enumerate(self._train_loader):
                
                loss, _ = self._base_model(**batch)

                self._optimizer.zero_grad()
                loss.backward()
                self._optimizer.step()
                self._lr_scheduler.step()
                
                self._l_train_loss.compute(loss=loss, epoch=epoch)
            
            self._l_test_loss.compute(test_loader=self._test_loader, epoch=epoch)
            
            self._l_ntk.flush()
            self._l_test_loss.flush()
            self._l_train_loss.flush()
            

def get_available_cuda_device() -> int:
    max_devs = torch.cuda.device_count()
    for i in range(max_devs):
        try:
            mem = torch.cuda.mem_get_info(i)
        except:
            continue
        if mem[0] / mem[1] > 0.85:
            return i
    return -1

def set_seed(seed: int) -> None:
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True

import sys

if __name__ == "__main__":
    set_seed(10315)
    
    n = "110"
    # n = sys.argv[1]
    
    availabe_device = get_available_cuda_device()
    if availabe_device < 0:
        raise Exception("no available devices")
    torch.cuda.set_device(availabe_device)
    
    b = bert_test(model_name="bert_test_" + n, config_file="config/bert.json")
    
    b.init_model()
    b.train()