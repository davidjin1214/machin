import torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.weight_norm import weight_norm

from .base import NeuralNetworkModule


def conv3x3(in_planes, out_planes, stride=1):
    """
    Create a 3x3 2d convolution block
    """
    return nn.Conv2d(in_planes, out_planes,
                     kernel_size=3, stride=stride, padding=1, bias=False)


def conv5x5(in_planes, out_planes, stride=2):
    """
    Create a 5x5 2d convolution block
    """
    return nn.Conv2d(in_planes, out_planes,
                     kernel_size=5, stride=stride, padding=2, bias=False)


def cfg(depth, use_batch_norm=True):
    depth_lst = [18, 34, 50, 101, 152]
    assert (depth in depth_lst), "Error : Resnet depth should be either 18, 34, 50, 101, 152"
    if use_batch_norm:
        cfg_dict = {
            '18': (BasicBlock, [2, 2, 2, 2]),
            '34': (BasicBlock, [3, 4, 6, 3]),
            '50': (Bottleneck, [3, 4, 6, 3]),
            '101': (Bottleneck, [3, 4, 23, 3]),
            '152': (Bottleneck, [3, 8, 36, 3]),
        }
    else:
        cfg_dict = {
            '18': (BasicBlockWN, [2, 2, 2, 2]),
            '34': (BasicBlockWN, [3, 4, 6, 3]),
            '50': (BottleneckWN, [3, 4, 6, 3]),
            '101': (BottleneckWN, [3, 4, 23, 3]),
            '152': (BottleneckWN, [3, 8, 36, 3]),
        }
    return cfg_dict[str(depth)]


class BasicBlock(NeuralNetworkModule):
    expansion = 1  # expansion parameter, output will have "expansion * in_planes" depth

    def __init__(self, in_planes, out_planes, stride=1):
        """
        Create a basic block of resnet.

        Args:
            in_planes:  number of input planes.
            out_planes: number of output planes.
            stride:     stride of convolution.
        """
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(in_planes, out_planes, stride)
        self.bn1 = nn.BatchNorm2d(out_planes)
        self.conv2 = conv3x3(out_planes, out_planes)
        self.bn2 = nn.BatchNorm2d(out_planes)
        # create a shortcut from input to output
        # an empty sequential structure means no transformation is made on input X
        self.shortcut = nn.Sequential()

        self.set_input_module(self.conv1)

        # a convolution is needed if we cannot directly add input X to output
        # BatchNorm2d produces NaN gradient?
        if stride != 1 or in_planes != self.expansion * out_planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion * out_planes,
                          kernel_size=1, stride=stride, bias=False),
                #nn.BatchNorm2d(self.expansion * out_planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class Bottleneck(NeuralNetworkModule):
    expansion = 4  # expansion parameter, output will have "expansion * in_planes" depth

    def __init__(self, in_planes, out_planes, stride=1):
        """
        Create a bottleneck block of resnet.

        Args:
            in_planes:  number of input planes.
            out_planes: number of output planes.
            stride:     stride of convolution.
        """
        super(Bottleneck, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, out_planes,
                               kernel_size=1, bias=False)
        self.conv2 = nn.Conv2d(out_planes, out_planes,
                               kernel_size=3, stride=stride, padding=1, bias=False)
        self.conv3 = nn.Conv2d(out_planes, self.expansion * out_planes,
                               kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_planes)
        self.bn2 = nn.BatchNorm2d(out_planes)
        self.bn3 = nn.BatchNorm2d(self.expansion * out_planes)

        self.shortcut = nn.Sequential()

        self.set_input_module(self.conv1)

        if stride != 1 or in_planes != self.expansion * out_planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion * out_planes,
                          kernel_size=1, stride=stride, bias=False),
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class BasicBlockWN(NeuralNetworkModule):
    """
    Basic block with weight normalization
    """
    expansion = 1  # expansion parameter, output will have "expansion * in_planes" depth

    def __init__(self, in_planes, out_planes, stride=1):
        """
        Create a basic block of resnet.

        Args:
            in_planes:  number of input planes.
            out_planes: number of output planes.
            stride:     stride of convolution.
        """
        super(BasicBlockWN, self).__init__()
        self.conv1 = weight_norm(conv3x3(in_planes, out_planes, stride))
        self.conv2 = weight_norm(conv3x3(out_planes, out_planes))
        # create a shortcut from input to output
        # an empty sequential structure means no transformation is made on input X
        self.shortcut = nn.Sequential()

        self.set_input_module(self.conv1)

        # a convolution is needed if we cannot directly add input X to output
        if stride != 1 or in_planes != self.expansion * out_planes:
            self.shortcut = nn.Sequential(
                weight_norm(nn.Conv2d(in_planes, self.expansion * out_planes,
                                      kernel_size=1, stride=stride, bias=False)),
            )

    def forward(self, x):
        out = F.relu(self.conv1(x))
        out = self.conv2(out)
        out += self.shortcut(x)
        out = F.relu(out)
        return out


class BottleneckWN(NeuralNetworkModule):
    """
    Bottleneck block with weight normalization
    """
    expansion = 4  # expansion parameter, output will have "expansion * in_planes" depth

    def __init__(self, in_planes, out_planes, stride=1):
        """
        Create a bottleneck block of resnet.

        Args:
            in_planes:  number of input planes.
            out_planes: number of output planes.
            stride:     stride of convolution.
        """
        super(BottleneckWN, self).__init__()
        self.conv1 = weight_norm(nn.Conv2d(in_planes, out_planes,
                                           kernel_size=1, bias=False))
        self.conv2 = weight_norm(nn.Conv2d(out_planes, out_planes,
                                           kernel_size=3, stride=stride, padding=1, bias=False))
        self.conv3 = weight_norm(nn.Conv2d(out_planes, self.expansion * out_planes,
                                           kernel_size=1, bias=False))

        self.shortcut = nn.Sequential()

        self.set_input_module(self.conv1)

        if stride != 1 or in_planes != self.expansion * out_planes:
            self.shortcut = nn.Sequential(
                weight_norm(nn.Conv2d(in_planes, self.expansion * out_planes,
                                      kernel_size=1, stride=stride, bias=False)),
            )

    def forward(self, x):
        out = F.relu(self.conv1(x))
        out = F.relu(self.conv2(out))
        out = self.conv3(out)
        out += self.shortcut(x)
        out = F.relu(out)

        return out


class ResNet(NeuralNetworkModule):
    def __init__(self, in_planes, depth, out_planes, out_pool_size=(1, 1), use_batch_norm=True):
        """
        Create a resnet of specified depth.

        Args:
            in_planes:  number of input planes.
            depth:      depth of resnet. eg: 18, 34, 50...
            out_planes: number of output planes.
            out_pool_size: size of pooling output
        """
        super(ResNet, self).__init__()
        self.in_planes = 64
        self.out_pool_size = out_pool_size

        block, num_blocks = cfg(depth, use_batch_norm)

        self.conv1 = conv3x3(in_planes, 64, 2)
        if use_batch_norm:
            self.bn1 = nn.BatchNorm2d(64)
            self.layer1 = self._make_layer(block, 64, num_blocks[0], 2)
            self.layer2 = self._make_layer(block, 128, num_blocks[1], 2)
            self.layer3 = self._make_layer(block, 256, num_blocks[2], 2)
            self.layer4 = self._make_layer(block, 512, num_blocks[3], 2)
            self.base = nn.Sequential(self.conv1, self.bn1, nn.ReLU(), self.layer1, self.layer2,
                                      self.layer3, self.layer4)
        else:
            self.layer1 = self._make_layer(block, 64, num_blocks[0], 2)
            self.layer2 = self._make_layer(block, 128, num_blocks[1], 2)
            self.layer3 = self._make_layer(block, 256, num_blocks[2], 2)
            self.layer4 = self._make_layer(block, 512, num_blocks[3], 2)
            self.base = nn.Sequential(self.conv1, nn.ReLU(), self.layer1, self.layer2,
                                      self.layer3, self.layer4)
        self.fc = nn.Linear(512 * out_pool_size[0] * out_pool_size[1], out_planes)

        self.set_input_module(self.conv1)

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1] * (num_blocks - 1)
        layers = []

        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.base(x)
        kernel_size = (np.int(np.floor(x.size(2) / self.out_pool_size[0])),
                       np.int(np.floor(x.size(3) / self.out_pool_size[1])))
        x = F.avg_pool2d(x, kernel_size)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x