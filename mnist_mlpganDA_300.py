import torch
import torch.utils.data as data
import torch.nn as nn
import torchvision
import torchvision.datasets as datasets
import torchvision.transforms as transforms
from torchvision.datasets import MNIST
from PIL import Image
import matplotlib.pyplot as plt
import numpy
import random
import glob
import shutil
import os
from distutils import dir_util

for i in range(10):
  src_dir1 = './images-cGAN-30/epochs:200/' + str(i)
  src_dir2 = './mnist_sampled/' + str(i)
  dst_dir = './DA_mnist_sampled/' + str(i) 
  os.makedirs(dst_dir, exist_ok=True)

  dir_util.copy_tree(src_dir1, dst_dir)
  dir_util.copy_tree(src_dir2, dst_dir)

for i in range(10):
    l = len(glob.glob('./mnist_sampled/' + str(i) + '/**', recursive=True))
    print('./mnist_sampled/{}: {}'.format(i, l))

for i in range(10):
    l = len(glob.glob('./DA_mnist_sampled/' + str(i) + '/**', recursive=True))
    print('./DA_mnist_sampled/{}: {}'.format(i, l))

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

#Hyper Parameters
num_epochs = 50 #エポック数:何周学習するか
num_classes = 10 #クラス数:0~9の10クラス
batch_size = 50 #バッチサイズ:いくつまとめて処理するか
learning_rate = 0.001 #学習率:1回の学習でどれだけ学習するか、どれだけパラメータを更新するか

#画像をテンソル化した際の処理
class ImageTransform():
    def __init__(self, mean, std):
        self.data_transform = transforms.Compose([
            transforms.Grayscale(1),
            transforms.ToTensor(),
            transforms.Normalize(mean, std)
        ])
    def __call__(self, img):
        return self.data_transform(img)

#ImageFolderを使ってデータの取り込み
mean = (0.5,)
std = (0.5,)
all_datasets = datasets.ImageFolder('./DA_mnist_sampled', transform = ImageTransform(mean, std))

test_datasets = MNIST(root='./', train=False, transform=transforms.ToTensor(), download=True)

random.seed(1)
numpy.random.seed(1)
torch.manual_seed(1)
torch.cuda.manual_seed(1)
torch.backends.cudnn.deterministic = True

n_samples = len(all_datasets)
train_size = int(n_samples * 0.8)
val_size = n_samples - train_size

#Trainとvalに分割
train_dataset, val_dataset = data.random_split(
    all_datasets,
    [train_size, val_size]
)

#Dataloaderの作成
train_dataloader = data.DataLoader(train_dataset, batch_size = batch_size, shuffle = True)
val_dataloader = data.DataLoader(val_dataset, batch_size = batch_size, shuffle=True)
test_dataloader = data.DataLoader(test_datasets, batch_size = batch_size, shuffle = False)

#ネットワーク構築
class ConvNet(nn.Module):
	def __init__ (self, num_classes=10):
		super(ConvNet, self).__init__()
		self.layer1 = nn.Sequential(
			nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),#32*32*16
			nn.BatchNorm2d(16),
			nn.ReLU())
		self.layer2 = nn.Sequential(
			nn.Conv2d(16, 16, kernel_size=3, stride=1, padding=1),#32*32*16
			nn.BatchNorm2d(16),
			nn.ReLU(),
			nn.MaxPool2d(kernel_size=2, stride=2)) #16*16*16
		self.layer3 = nn.Sequential(
			nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),#16*16*32
			nn.BatchNorm2d(32),
			nn.ReLU())
		self.layer4 = nn.Sequential(
			nn.Conv2d(32, 32, kernel_size=3, stride=1, padding=2),#18*18*32
			nn.BatchNorm2d(32),
			nn.ReLU(),
			nn.MaxPool2d(kernel_size=2, stride=2))#10*10*32
		self.layer5 = nn.Sequential(
			nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),#10*10*64
			nn.BatchNorm2d(64),
			nn.ReLU())
		self.layer6 = nn.Sequential(
			nn.Conv2d(64, 64, kernel_size=3, stride=1, padding=1),#10*10*64
			nn.BatchNorm2d(64),
			nn.ReLU(),
			nn.MaxPool2d(kernel_size=2, stride=2))#5*5*64
		self.fc1 = nn.Sequential(
			nn.Linear(4*4*64, 2048),
			nn.ReLU(),
			nn.Dropout2d(p=0.5))
		self.fc2 = nn.Sequential(
			nn.Linear(2048, num_classes),
			nn.Dropout2d(p=0.5))

	def forward(self, x):
		out = self.layer1(x)
		out = self.layer2(out)
		out = self.layer3(out)
		out = self.layer4(out)
		out = self.layer5(out)
		out = self.layer6(out)
		out = out.reshape(out.size(0), -1)
		out = self.fc1(out)
		out = self.fc2(out)
		return out

model = ConvNet(num_classes).to(device)

#Loss and optimizer
criterion = nn.CrossEntropyLoss() #交差エントロピー誤差
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate) #Adamによる最適化

#Training
print('training start ...')

#initialize list for plot graph after training
train_loss_list, train_acc_list, val_loss_list, val_acc_list = [], [], [], []

for epoch in range(num_epochs):
    #initialize each epoch
    train_loss, train_acc, val_loss, val_acc = 0, 0, 0, 0

    # -----  train mode -----
    model.train()
    for i, (images, labels) in enumerate(train_dataloader):
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad() #勾配リセット
        outputs = model(images) #順伝搬の計算
        loss = criterion(outputs, labels) #lossの計算
        train_loss += loss.item() #train_lossに結果を蓄積
        acc = (outputs.max(1)[1] == labels).sum()   #予測とラベルがあっている数の合計
        train_acc = acc.item() #train_accに結果を蓄積
        loss.backward() #逆伝搬の計算
        optimizer.step() #重みの更新
    
    avg_train_loss = train_loss / len(train_dataloader.dataset) #lossの平均を計算
    avg_train_acc = train_acc / len(train_dataloader.dataset) #accの平均を計算

    # ----- valid_mode -----
    model.eval()
    with torch.no_grad(): #必要のない計算を停止
        for images, labels in val_dataloader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            val_loss += loss.item()
            acc = (outputs.max(1)[1] == labels).sum()
            val_acc += acc.item()
    avg_val_loss = val_loss / len(val_dataloader.dataset)
    avg_val_acc = val_acc / len(val_dataloader.dataset)

    #print log
    print('Epoch [{}/{}], Loss: {loss:.4f}, val_loss: {val_loss:.4f}, val_acc: {val_acc:.4f}'
    .format(epoch+1, num_epochs, i+1, loss=avg_train_loss, val_loss=avg_val_loss, val_acc=avg_val_acc))

    # append list for plot graph after training
    train_loss_list.append(avg_train_loss)
    train_acc_list.append(avg_train_acc)
    val_loss_list.append(avg_val_loss)
    val_acc_list.append(avg_val_acc)

# ----- test mode -----
model.eval()
with torch.no_grad():
    total = 0
    test_acc = 0
    for images, labels in test_dataloader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        test_acc += (outputs.max(1)[1] == labels).sum().item()
        total += labels.size(0)
    print('test_accuracy: {} %'.format(100 * test_acc / total))

#save weights
torch.save(model.state_dict(), 'mnist_baseline.ckpt')

# plot graph
 
plt.figure()
plt.plot(range(num_epochs), train_loss_list, color='blue', linestyle='-', label='train_loss')
plt.plot(range(num_epochs), val_loss_list, color='green', linestyle='--', label='val_loss')
plt.legend()
plt.xlabel('epoch')
plt.ylabel('loss')
plt.title('Training and validation loss')
plt.grid()
plt.show() 

plt.figure()
plt.plot(range(num_epochs), train_acc_list, color='blue', linestyle='-', label='train_acc')
plt.plot(range(num_epochs), val_acc_list, color='green', linestyle='--', label='val_acc')
plt.legend()
plt.xlabel('epoch')
plt.ylabel('acc')
plt.title('Training and validation accuracy')
plt.grid()
plt.show()