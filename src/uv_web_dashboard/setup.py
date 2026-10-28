import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'uv_web_dashboard'

def get_frontend_files():
    paths = []
    dist_dir = os.path.join('web_frontend', 'dist')
    if os.path.exists(dist_dir):
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                rel_file = os.path.join(root, file)
                if os.path.isfile(rel_file):
                    rel_dir = os.path.relpath(root, '.')
                    paths.append((os.path.join('share', package_name, rel_dir), [rel_file]))
    return paths

data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
] + get_frontend_files()

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='aziz',
    maintainer_email='aziz@todo.todo',
    description='UV Disinfection Robot Web Dashboard and Mission Control Package',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'disinfection_process = uv_web_dashboard.disinfection_process:main',
        ],
    },
)
