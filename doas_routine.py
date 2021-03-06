# Main Subroutine which processes images according to the DOAS retrieval method.

import numpy as np
from scipy import signal
import os
import glob
import cv2
import tkinter as tk
from tkinter import filedialog
import matplotlib.pyplot as plt

class DOASWorker:
    """Class to control DOAS processing
    General order of play for processing:
    Initiate class,
    get_ref_spectrum()
    set_fit_window()
    shift_spectrum"""
    def __init__(self, routine):
        self.routine = routine  # Defines routine to be used, either (1) Polynomial or (2) Digital Filtering

        # ======================================================================================================================
        # Initial Definitions
        # ======================================================================================================================
        self.row_range = np.arange(300, 311)  # Number of rows to be averaged when generating the spectrum form the image
        self.stray_range = np.arange(100, 201)  # Columns to be used for stray light correction
        self.shift = 0  # Shift of spectrum in number of pixels
        self.start_fit_pix = 275
        self.end_fit_pix = 400  # Pixel space fitting window definitions
        self.start_fit_wave = 305
        self.end_fit_wave = 320  # Wavelength space fitting window definitions
        self.fit_window = None  # Fitting window, determined by set_fit_window()
        self.fit_window_ref = None  # Placeholder for shifted fitting window for the reference spectrum
        self.wave_fit = True  # If True, wavelength parameters are used to define fitting window

        self.wavelengths = None  # Placeholder for wavelengths attribute which contains all wavelengths of spectra

        self.poly_order = 2  # Order of polynomial used to fit residual
        (self.filt_B, self.filt_A) = signal.butter(10, 0.065, btype='highpass')

        self.start_ca = 0  # Starting column amount for iterations
        self.end_ca = 2000  # Ending column amount for iterations
        self.vals_ca = np.arange(self.start_ca, self.end_ca+1)  # Array of column amounts to be iterated over
        self.mse_vals = np.zeros(len(self.vals_ca))  # Array to hold mse values

        self.filetypes = dict(defaultextension='.png', filetypes=[('PNG', '*.png')])
        # ==============================================================================================================

        # --------------------------------------------------------------------------------------------------------------
        # GENERATE CLEAR SPECTRUM AND LOAD DARK IMAGE
        (self.img_clear, self.img_size_x, self.img_size_y) = self.load_img()  # Clear image (I0)
        self.img_dark = self.load_dark()  # Dark Image
        self.img_clear = self.img_clear - self.img_dark  # Dark subtract clear image
        self.clear_spec = np.mean(self.img_clear[self.row_range, :])
        # --------------------------------------------------------------------------------------------------------------

    def get_ref_spectrum(self):
        """Load in reference spectrum"""
        self.wavelengths = None  # Placeholder for wavelengths attribute which contains all wavelengths of spectra
        #
        # --------------------------------

    def set_fit_window(self):
        """Define fitting window for DOAS procedure
        If wavelength domain is used, first convert this to pixel space"""
        if self.wave_fit:
            if self.wavelengths is None:
                print('Error, first run get_ref_spectrum() to define wavelengths vector')
                return
            wave_dif_start = self.wavelengths - self.start_fit_wave
            wave_dif_end = self.wavelengths - self.end_fit_wave
            self.start_fit_pix = wave_dif_start.index(np.amin(wave_dif_start))  # Find the index which represents the wavelengths closest to the defined starting wavelength for the fit
            self.end_fit_pix = wave_dif_end.index(np.amin(wave_dif_end))  # As above, but for ending wavelength

        self.fit_window = np.arange(self.start_fit_pix, self.end_fit_pix)  # Fitting window (in Pixel space)

    def shift_spectrum(self):
        """Shift fitting window for reference spectrum"""
        self.fit_window_ref = self.fit_window - self.shift  # Shifting the fitting window indices for the ref spectrum

    def load_img(self):
        """Load img"""
        root = tk.Tk()
        root.withdraw()
        img_path = filedialog.askopenfilename(**self.filetypes)  # Get user to find clear image
        img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)  # Read in clear image
        size_y, size_x = np.shape(img)  # Define image dimensions
        return img, size_x, size_y

    def load_dark(self):
        """Load drk images -> co-add to generate single dark image"""
        dark_dir_path = filedialog.askdirectory()
        dark_dir_path += '/*.png'
        dark_list = glob.glob(dark_dir_path)   # List all .png files in dark directory
        num_dark_imgs = len(dark_list)
        dark_array = np.zeros([self.img_size_y, self.img_size_x, num_dark_imgs])
        for i in range(num_dark_imgs):
            dark_array[:, :, i] = cv2.imread(dark_dir_path + '/' + dark_list[i], cv2.IMREAD_UNCHANGED)
        img_dark = np.mean(dark_array, 2)
        return img_dark

    def poly_DOAS(self):
        """Performs main processing in polynomial fitting DOAS retrieval"""

        self.abs_spec = np.log(np.divide(self.clear_spec, self.plume_spec))  # Calculate absorbance
        self.ref_spec_cut = self.ref_spec[self.fit_window_ref]
        self.abs_spec_cut = self.abs_spec[self.fit_window]

        idx = 0
        for i in self.vals_ca:
            ref_spec_fit = self.ref_spec_cut * i  # Our iterative guess at the SO2 column density
            residual = self.abs_spec_cut - ref_spec_fit  # Calculate resultant residual from spectrum fitting
            poly_fit = np.polyfit(self.fit_window, residual, self.poly_order)  # Fit polynomial to residual
            poly_vals = np.polyval(poly_fit, self.fit_window)  # Generate polynomial values for fitting window

            self.mse_vals[idx] = np.mean(np.power(residual - poly_vals, 2))  # Calculate MSE of fit

            idx += 1

        self.min_idx = np.argmin(self.mse_vals)
        self.column_amount = self.vals_ca[self.min_idx]

    def fltr_DOAS(self):
        """Performs main retrieval in digital filtering DOAS retrieval"""
        self.abs_spec = np.log(np.divide(self.clear_spec, self.plume_spec))  # Calculate absorbance
        self.abs_spec_filt = signal.lfilter(self.filt_B, self.filt_A, self.abs_spec)  # Filter absorbance spectrum

        self.ref_spec_cut = self.ref_spec[self.fit_window_ref]
        self.abs_spec_cut = self.abs_spec[self.fit_window]

        idx = 1
        for i in self.vals_ca:
            ref_spec_fit = self.ref_spec_cut * i

            self.mse_vals[idx] = np.mean(np.power(self.abs_spec_cut, ref_spec_fit, 2))  # Calculate MSE of fit
            idx += 1

        self.min_idx = np.argmin(self.mse_vals)
        self.column_amount = self.vals_ca[self.min_idx]



    def poly_plot_gen(self):
        """Generate arrays to be plotted -> residual, fitted spectrum"""
        self.ref_spec_fit = self.ref_spec_cut * self.column_amount
        self.residual = self.abs_spec_cut - self.ref_spec_fit
        poly_fit = np.polyfit(self.fit_window, self.residual, self.poly_order)  # Fit polynomial to residual
        self.poly_vals = np.polyval(poly_fit, self.fit_window)  # Generate polynomial values for fitting window
        self.best_fit = self.ref_spec_fit + self.poly_vals  # Generate best fit absorbance spectrum

        # MAKE PLOT
        plt.figure()
        abs_plt, = plt.plot(self.abs_spec_cut, label='Absorbance spectrum')
        ref_plt, = plt.plot(self.ref_spec_fit, label='Reference spectrum * CA')
        res_plt, = plt.plot(self.residual, label='Residual')
        poly_plt, = plt.plot(self.poly_vals, label='Polynomial fit')
        best_plt, = plt.plot(self.best_fit, label='Best fit')
        plt.xlabel('Pixel')
        plt.ylabel('Absorbance')
        plt.legend(handles=[abs_plt, ref_plt, res_plt, poly_plt, best_plt])
        plt.show()





class SpectrometerCal:
    """Class to calibrate spectrometer"""
    def __init__(self):
        pass


if __name__ == "__main__":
    doas_process = DOASWorker(2)
    doas_process.get_ref_spectrum()
    doas_process.set_fit_window()
    doas_process.shift_spectrum()