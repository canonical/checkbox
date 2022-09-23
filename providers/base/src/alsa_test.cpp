#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <istream>
#include <iterator>
#include <limits>
#include <map>
#include <string>
#include <sstream>
#include <thread>
#include <vector>
#include <alsa/asoundlib.h>
#include <complex>
#include <valarray>

typedef std::valarray<std::complex<float>> CArray;
void fft(CArray& x)
{
    // almost the same implementation as one on rosetta code
    const size_t N = x.size();
    if (N <= 1) return;
    CArray even = x[std::slice(0, N/2, 2)];
    CArray odd = x[std::slice(1, N/2, 2)];
    fft(even);
    fft(odd);
    for (size_t k = 0; k < N/2; ++k) {
        auto t = std::polar(1.0f, -2 * float(M_PI) * k / N) * odd[k];
        x[k] = even[k] + t;
        x[k+N/2] = even[k] - t;
    }
}

struct Logger {
    enum class Level {normal, info, debug};
    void set_level(Level new_lvl) {
        level = new_lvl;
    }
    std::ostream& info() {
        if (this->level >= Level::info) {
            return std::cout;
        } else {
            return this->nullStream;
        }
    }
    std::ostream& normal() {
            return std::cout;
    }
    Logger() : level(Level::normal) {}
    Logger(const Logger& l) {}

private:
    Level level;
    struct NullStream : std::ostream {
        template<typename T>
        NullStream& operator<<(T const&) {
            return *this;
        }
    };
    NullStream nullStream;
};

Logger logger = Logger();

std::vector<std::pair<std::string, std::string>> all_formats = {
    {"float_44100", "Float32 encoded, 44100Hz sampling"},
    {"float_48000", "Float32 encoded, 48000Hz sampling"},
    {"int16_44100", "Signed Int16 encoded, 44100Hz sampling"},
    {"int16_48000", "Signed Int16 encoded, 48000Hz sampling"},
    {"uint16_44100", "Unsigned Int16 encoded, 44100 sampling"},
    {"uint16_48000", "Unsigned Int16 encoded, 48000 sampling"}
};

namespace Alsa{

using std::string;

struct AlsaError: std::runtime_error {
    explicit AlsaError(const string& what_arg) : runtime_error(what_arg) {}
};

template<class storage_type>
struct Pcm {
    enum class Mode {playback, capture};

    Pcm() : Pcm{"default", Mode::playback} {}
    Pcm(string device_name, Mode mode = Mode::playback) {
        snd_pcm_stream_t stream_mode;
        switch(mode) {
            case Mode::playback:
                stream_mode = SND_PCM_STREAM_PLAYBACK;
                break;
            case Mode::capture:
                stream_mode = SND_PCM_STREAM_CAPTURE;
                break;
        }

        int res = snd_pcm_open(&this->pcm_handle, device_name.c_str(),
                stream_mode, 0 /* blocking */);
        if (res < 0) {
            auto ec = std::error_code(-res, std::system_category());
            auto msg = string("Failed to open device: ") + string(device_name)
                + string(". ") + string(snd_strerror(res));
            throw AlsaError(msg);
        }
        logger.info() << "PCM opened. Name: " << device_name << " PCM handle: "
            << pcm_handle << " PCM mode: "
            << (int(mode) ? "capture" : "playback") << std::endl;
    }
    ~Pcm() {
        switch (mode) {
            case Mode::playback:
                logger.info() << "Draining PCM " << pcm_handle << std::endl;
                snd_pcm_drain(this->pcm_handle);
                break;
            case Mode::capture:
                logger.info() << "Dropping PCM " << pcm_handle << std::endl;
                snd_pcm_drop(this->pcm_handle);
                break;
        }
        logger.info() << "Closing PCM " << pcm_handle << std::endl;
        snd_pcm_close(this->pcm_handle);
    }
    void drain() {
        snd_pcm_drain(this->pcm_handle);
    }
    void set_params(const unsigned desired_rate) {
        snd_pcm_hw_params_t *params = nullptr;
        snd_pcm_hw_params_alloca(&params);
        snd_pcm_hw_params_any(this->pcm_handle, params);
        if (snd_pcm_hw_params_set_access(this->pcm_handle, params,
            SND_PCM_ACCESS_RW_INTERLEAVED) < 0) {
            throw AlsaError("Failed to set access mode");
        }
        if (snd_pcm_hw_params_set_channels(this->pcm_handle, params, 2) < 0) {
            throw AlsaError("Failed to set the number of channels");
        }
        if (auto res = snd_pcm_hw_params_set_format(this->pcm_handle, params,
            get_alsa_format()) < 0) {
            throw AlsaError(string("Failed to set format") + string(
                snd_strerror(res)));
        }
        this->rate = desired_rate;
        // pick will determine how alsa picks value,
        // 0: exact value, -1: closest smaller value, +1: closest bigger value
        int pick = 0;
        if (snd_pcm_hw_params_set_rate_near(this->pcm_handle, params,
            &this->rate, &pick) < 0) {
            throw AlsaError("Failed to set rate");
        }
        if (snd_pcm_hw_params(this->pcm_handle, params) < 0) {
            throw AlsaError("Failed to write params to ALSA");
        }
        logger.info() << "got rate: " << rate << std::endl;
        snd_pcm_uframes_t frames;
        int dir;
        auto res = snd_pcm_hw_params_get_period_size(params, &frames, &dir);
        this->period = frames;
        unsigned period_time;
        snd_pcm_hw_params_get_period_time(params, &period_time, NULL);
        logger.info() << "period_time: " << period_time << std::endl;
        logger.info() << "state: " <<
            snd_pcm_state_name(snd_pcm_state(this->pcm_handle)) << std::endl;
        unsigned channs;
        snd_pcm_hw_params_get_channels_max(params, &channs);
        logger.info() << "no. of channels: " << channs << std::endl;
    }
    void sine(const float freq, const float duration, const float amplitude) const {
        auto *buff = new storage_type[this->period * 2];
        void *ugly_ptr = static_cast<void*>(buff);
        unsigned t = 0;
        while (t < float(this->rate) * duration) {
            for (int i=0; i < this->period * 2; i+=2) {
                auto sample = sin(2 * M_PI *((t + i/2) / (this->rate / freq)));
                // we need to convert the sample to the target range, -1.0f should
                // match the min_val and +1.0f should match the max_val
                auto target_range = float(this->max_val()) - float(this->min_val());
                sample = target_range * ((sample + 1.0f)/2.0f) + float(min_val());
                // saturate/trim
                if (sample > float(max_val()))
                    sample = max_val();
                else if (sample < float(min_val()))
                    sample = min_val();
                // set volume
                sample *= amplitude;
                buff[i] = sample;
                buff[i+1] = buff[i]; // the other channel
            }
            auto res = snd_pcm_writei(this->pcm_handle, ugly_ptr, this->period);
            if (res == -EPIPE) {
                logger.info() << "Buffer underrun" << std::endl;
                snd_pcm_prepare(this->pcm_handle);
            }
            t += this->period;
        }
        logger.info() << "state: " <<
            snd_pcm_state_name(snd_pcm_state(this->pcm_handle)) << std::endl;
        snd_pcm_start(this->pcm_handle);
        delete[] buff;
    }
    void record(storage_type *buff, int buff_size /*in samples*/) {
        auto *local_buff = new storage_type[this->period * 2];
        int res;
        snd_pcm_start(this->pcm_handle);
        logger.info() << "state: " <<
            snd_pcm_state_name(snd_pcm_state(this->pcm_handle)) << std::endl;

        while(buff_size > 0) {
            if (buff_size >= this->period * 2) {
                void *ugly_ptr = static_cast<void*>(buff);
                res = snd_pcm_readi(this->pcm_handle, ugly_ptr, this->period);
                buff_size -= this->period * 2;
                buff += this->period *2;
            } else {
                void *ugly_ptr = static_cast<void*>(local_buff);
                res = snd_pcm_readi(this->pcm_handle, ugly_ptr, this->period);
                std::memcpy(buff, local_buff, buff_size * sizeof(storage_type));
                buff_size = 0;
            }
        }
        delete[] local_buff;
    }
    void play(storage_type *buff, int buff_size) {
        snd_pcm_prepare(this->pcm_handle);
        while (buff_size > 0) {
            void *ugly_ptr = static_cast<void*>(buff);
            auto res = snd_pcm_writei(this->pcm_handle, ugly_ptr, this->period);
            buff_size -= this->period *2;
            buff += this->period * 2;
        }
        logger.info() << "state: " <<
            snd_pcm_state_name(snd_pcm_state(this->pcm_handle)) << std::endl;
    }


private:
    snd_pcm_format_t get_alsa_format();
    bool is_little_endian() {
        #if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
            return true;
        #else
            return false;
        #endif
    }
    storage_type min_val() const { return std::numeric_limits<storage_type>::min();}
    storage_type max_val() const { return std::numeric_limits<storage_type>::max();}

    snd_pcm_t *pcm_handle;
    unsigned rate;
    snd_pcm_uframes_t period;
    Mode mode;
};

template<>
float Alsa::Pcm<float>::min_val() const { return -1.0f; }

template<>
float Alsa::Pcm<float>::max_val() const { return 1.0f; }

template<>
snd_pcm_format_t Alsa::Pcm<float>::get_alsa_format() {
    return is_little_endian() ? SND_PCM_FORMAT_FLOAT_LE : SND_PCM_FORMAT_FLOAT_BE;
}
template<>
snd_pcm_format_t Alsa::Pcm<double>::get_alsa_format() {
    return is_little_endian() ? SND_PCM_FORMAT_FLOAT64_LE : SND_PCM_FORMAT_FLOAT64_BE;
}
template<>
snd_pcm_format_t Alsa::Pcm<int16_t>::get_alsa_format() {
    return is_little_endian() ? SND_PCM_FORMAT_S16_LE : SND_PCM_FORMAT_S16_BE;
}
template<>
snd_pcm_format_t Alsa::Pcm<uint16_t>::get_alsa_format() {
    return is_little_endian() ? SND_PCM_FORMAT_U16_LE : SND_PCM_FORMAT_U16_BE;
}
template<>
snd_pcm_format_t Alsa::Pcm<int8_t>::get_alsa_format() {
    return SND_PCM_FORMAT_S8;
}
template<>
snd_pcm_format_t Alsa::Pcm<uint8_t>::get_alsa_format() {
    return SND_PCM_FORMAT_U8;
}

struct Mixer {
    Mixer(string card_name, string mixer_name) {
        int res;
        res = snd_mixer_open(&mixer_handle, 0);
        if (res < 0) throw AlsaError("Failed to open an empty Mixer");
        res = snd_mixer_attach(mixer_handle, card_name.c_str());
        if (res < 0) throw AlsaError("Failed to attach HCTL to a Mixer");
        res = snd_mixer_selem_register(mixer_handle, NULL, NULL);
        if (res < 0) throw AlsaError("Failed to register a Mixer");
        res = snd_mixer_load(mixer_handle);
        if (res < 0) throw AlsaError("Failed to load a Mixer");
        snd_mixer_selem_id_alloca(&sid);
        snd_mixer_selem_id_set_index(sid, 0);
        snd_mixer_selem_id_set_name(sid, mixer_name.c_str());
        elem = snd_mixer_find_selem(mixer_handle, sid);
        if (!elem) throw AlsaError(mixer_name + " mixer not found.");
    }
    ~Mixer() {
        snd_mixer_close(mixer_handle);
    }
    void set_all_playback_volume(float volume) {
        long min, max;
        snd_mixer_selem_get_playback_volume_range(elem, &min, &max);
        int new_vol = int(float(max) * volume);
        snd_mixer_selem_set_playback_switch_all(elem, 1);
        snd_mixer_selem_set_playback_volume_all(elem, new_vol);
    }
    void set_all_capture_volume(float volume) {
        long min, max;
        snd_mixer_selem_get_capture_volume_range(elem, &min, &max);
        int new_vol = int(float(max) * volume);
        snd_mixer_selem_set_capture_switch_all(elem, 1);
        snd_mixer_selem_set_capture_volume_all(elem, new_vol);
    }
private:
    snd_mixer_t *mixer_handle;
    snd_mixer_selem_id_t *sid;
    snd_mixer_elem_t* elem;
};

std::vector<std::string> get_devices(std::string io) {
    std::vector<std::string> result;
    void **out;
    int err = snd_device_name_hint(-1 /* all cards */, "pcm", &out);
    if (err) {
        logger.normal() << "Couldn't get the device hints" << std::endl;
        return result;
    }
    while (*out) {
        const char *name = snd_device_name_get_hint(*out, "NAME");
        const char *desc = snd_device_name_get_hint(*out, "DESC");
        const char *ioid = snd_device_name_get_hint(*out, "IOID");
        if (ioid == nullptr) ioid = "Both";
        logger.info() << "Got a device hint. Name: " << name
                      << " Description: " << desc
                      << " IOID: " << ioid << std::endl;
        std::string direction{ioid};
        if (direction == io) {
           result.push_back(std::string{name});
        }
        out++;
    }
    return result;
}
}; //namespace Alsa

template<class storage_type>
int playback_test(float duration, int sampling_rate, const char* capture_pcm, const char* playback_pcm) {
    auto player = Alsa::Pcm<storage_type>();
    player.set_params(sampling_rate);
    player.sine(440, duration, 0.5f);
    return 0;
}

template<class storage_type>
float dominant_freq(storage_type *buff, int buffsize, int rate) {
    CArray data(buffsize);
    for (int i=0; i < buffsize; i++) {
        data[i] = std::complex<float>(buff[i], 0);
    }
    fft(data);
    auto freqs = std::vector<float>(buffsize/2); // drop mirrored freqs
    for (int i=0; i< buffsize / 2; i++){
        freqs[i] = std::abs(data[i]);
    }
    auto it = std::max_element(freqs.begin(), freqs.end());
    if (it != freqs.end()) {
        return float(std::distance(freqs.begin(), it)) / (float(buffsize) / rate);
    } else {
        return 0.0f;
    }
}
template<class storage_type>
int loopback_test(float duration, int sampling_rate, const char* capture_pcm, const char* playback_pcm) {
    const float test_freq = 440.0f;
    int buffsize = static_cast<int>(ceil(float(sampling_rate * 2) * duration));
    std::vector<storage_type> buff(buffsize);
    for (int attempt = 0; attempt < 3; ++attempt) {
        for (int i=0; i<buffsize; i++) buff[i] = storage_type(0);
        auto recorder = Alsa::Pcm<storage_type> (capture_pcm, Alsa::Pcm<storage_type>::Mode::capture);
        recorder.set_params(sampling_rate);
        std::thread rec_thread([&recorder, &buff, &buffsize]() mutable{
            recorder.record(&buff[0], buffsize);
        });
        try {
            auto player = Alsa::Pcm<storage_type>(playback_pcm);
            player.set_params(sampling_rate);
            player.sine(test_freq, duration, 0.5f);
            player.drain();
            rec_thread.join();
        }
        catch (Alsa::AlsaError& exc) {
            rec_thread.join();
            return 1;
        }
        float dominant = dominant_freq<storage_type>(&buff[0], buffsize, sampling_rate * 2);
        if (dominant > 0.0f) {
            //buff contains stereo samples, so the sampling rate can be considered 88200
            logger.normal() << "Dominant frequency: " << dominant << std::endl;
            // inverse-proportional to duration - the longer it runs,
            // the more accurate the fft gets
            float epsilon = 5 / duration + 1;
            float deviation = abs(test_freq - dominant);
            logger.normal() << "Deviation: " << deviation << std::endl;
            if (deviation <= epsilon)
                return 0;
        }
    }
    return 1;
}
template<class storage_type>
int fallback_loopback(float duration, int sampling_rate, const char* _1, const char* _2) {
    auto playback = Alsa::get_devices("Output");
    auto record = Alsa::get_devices("Input");
    auto both = Alsa::get_devices("Both");
    std::copy(both.begin(), both.end(), std::back_inserter(playback));
    std::copy(both.begin(), both.end(), std::back_inserter(record));
    for (auto player = playback.cbegin(); player != playback.cend(); ++player) {
        if (*player == std::string{"surround40:CARD=PCH,DEV=0"}) {
            continue;
        }
        for (auto recorder = record.cbegin(); recorder != record.cend(); ++recorder) {
            logger.normal() << "Trying combination " << *player << " -> " << *recorder << std::endl;
            try {
                int error = loopback_test<storage_type>(
                    duration, sampling_rate, recorder->c_str(), player->c_str());
                if (!error) {
                    return 0;
                }
            }
            catch(Alsa::AlsaError& exc) {
                logger.normal() << "Alsa problem: " << exc.what() << std::endl;
            }
        }
    }
    return 1;
}
int list_formats(){
    const char* env_var = std::getenv("ALSA_TEST_FORMATS");
    std::vector<std::string> picked_formats;

    if (env_var) {
        std::stringstream ss(env_var);
        std::istream_iterator<std::string> ss_iter(ss);
        std::istream_iterator<std::string> end;
        picked_formats = std::vector<std::string>(ss_iter, end);
    } else {
        // nothing specified in the envvar so let's just copy keys from all_formats
        for (auto it: all_formats) {
            picked_formats.push_back(it.first);
        }
    }

    for (auto format: all_formats) {
        if (find(picked_formats.begin(), picked_formats.end(), format.first) == picked_formats.end()) {
            // format not picked
            continue;
        }
        std::cout << "format: " << format.first << std::endl;
        std::cout << "description: " << format.second << std::endl;
        std::cout << std::endl;
    }
    return 0;
}

int list_devices() {
    auto playback = Alsa::get_devices("Output");
    auto record = Alsa::get_devices("Input");
    auto both = Alsa::get_devices("Both");
    std::copy(both.begin(), both.end(), std::back_inserter(playback));
    std::copy(both.begin(), both.end(), std::back_inserter(record));
    std::cout << "Playback devices: " << std::endl;
    for (auto i = playback.cbegin(); i != playback.cend(); ++i) {
        std::cout << *i << std::endl;
    }
    std::cout << "\n\nRecording devices: " << std::endl;
    for (auto i = record.cbegin(); i != record.cend(); ++i) {
        std::cout << *i << std::endl;
    }
    return 0;
}

void set_volumes(const std::string playback_pcm, const std::string capture_pcm) {
    try {
        auto playback_mixer = Alsa::Mixer(playback_pcm, "Master");
        auto capture_mixer = Alsa::Mixer(capture_pcm, "Capture");
        playback_mixer.set_all_playback_volume(0.75f);
        capture_mixer.set_all_capture_volume(0.75f);
    } catch(Alsa::AlsaError err) {
        logger.normal() << "Failed to change volume: " << err.what() << std::endl;
        // not being able to change the volume is not critical to the test
        // and for some devices "Master" and "Caputre" mixers may not exist
        // so let's just print warning if that's the case
    }
}

int main(int argc, char *argv[]) {
    std::vector<std::string> args{};
    for (int i=0; i < argc; ++i) {
        args.push_back(std::string(argv[i]));
    }
    if (std::find(args.begin(), args.end(), std::string("-v")) != args.end()) {
        logger.set_level(Logger::Level::info);
    }
    auto format = std::string("int16_48000");
    auto format_it = std::find(args.begin(), args.end(), std::string("--format"));
    if (format_it != args.end()) { // not doing && because of sequence points
        if (++format_it != args.end()) {
            format = std::string(*format_it);
            auto it = find_if(
                all_formats.begin(), all_formats.end(),
                [format](std::pair<std::string, std::string> p) {return p.first == format;});
            if (it == all_formats.end()) {
                std::cerr << "Unknown format: " << format << std::endl;
                return 1;
            }
        }
    }
    auto sample_format = std::string(format.begin(),  find(format.begin(), format.end(), '_'));
    auto sampling_rate = atoi(
        std::string(find(format.begin(), format.end(), '_') + 1, format.end()).c_str());
    logger.info() << "Using format: " << sample_format <<
                       " and sampling rate: " << sampling_rate << std::endl;
    std::map<std::string, int(*)(float, int, const char*, const char*)> scenarios;
    if (sample_format == "float") {
        scenarios["playback"] = playback_test<float>;
        scenarios["loopback"] = loopback_test<float>;
        scenarios["fallback"] = fallback_loopback<float>;
    }
    else if (sample_format == "int16") {
        scenarios["playback"] = playback_test<int16_t>;
        scenarios["loopback"] = loopback_test<int16_t>;
        scenarios["fallback"] = fallback_loopback<int16_t>;
    }
    else if (sample_format == "uint16") {
        scenarios["playback"] = playback_test<uint16_t>;
        scenarios["loopback"] = loopback_test<uint16_t>;
        scenarios["fallback"] = fallback_loopback<uint16_t>;
    }
    else {
        assert(!"MISSING IF-ELSES FOR FORMATS");
    }

    if (args.size() < 2) {
        std::cerr << "Required 'scenario' argument missing" << std::endl;
        return 1;
    }
    float duration = 1.0f;
    auto it = std::find(args.begin(), args.end(), std::string("-d"));
    if (it != args.end()) { // not doing && because of sequence points
        if (++it != args.end()) {
            duration = std::stof(*it);
        }
    }
    std::string capture_pcm{"default"};
    it = std::find(args.begin(), args.end(), std::string("--capture-pcm"));
    if (it != args.end()) {
        if (++it != args.end()) {
            capture_pcm = *it;
        }
    }
    std::string playback_pcm{"default"};
    it = std::find(args.begin(), args.end(), std::string("--playback-pcm"));
    if (it != args.end()) { // not doing && because of sequence points
        if (++it != args.end()) {
            playback_pcm = *it;
        }
    }
    set_volumes(playback_pcm, capture_pcm);
    std::string scenario{args[1]};
    if (scenario == "playback") {
        return scenarios["playback"](duration, sampling_rate, capture_pcm.c_str(), playback_pcm.c_str());
    }
    else if (scenario == "loopback") {
        int error = scenarios["loopback"](duration, sampling_rate, capture_pcm.c_str(), playback_pcm.c_str());
        if (!error) return 0;
        return scenarios["fallback"](duration, sampling_rate, nullptr, nullptr);
    }
    else if (scenario == "list-formats") {
        return list_formats();
    }
    else if (scenario == "list-devices") {
        return list_devices();
    }
    if (scenarios.find(args[1]) == scenarios.end()) {
        std::cerr << args[1] << " scenario not found!" << std::endl;
        return 1;
    }
}
