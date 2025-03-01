import time
import json
import requests
import utils.TaskQueue as TaskQueue

import websocket
import json
import numpy as np


class Live2dController:

    def __init__(self, live2d_model_name: str, base_url: str = "http://127.0.0.1:8000"):

        self.modelDictPath = "model_dict.json"
        self.base_url = base_url
        self.live2d_model_name = live2d_model_name

        self.model_info = self.setModel(live2d_model_name)

        self.emoMap = self.model_info["emotionMap"]

        self.received_data_buffer = np.array([])

        self.task_queue = TaskQueue.TaskQueue()

    def getEmoMapKeyAsString(self):
        """
        Returns a string of the keys in the emoMap dictionary.

        Parameters:
            None

            Returns:
            str: A string of the keys in the emoMap dictionary. The keys are enclosed in square brackets.
                example: `"[fear], [anger], [disgust], [sadness], [joy], [neutral], [surprise]"`

            Raises:
            None
        """
        return " ".join([f"[{key}]," for key in self.emoMap.keys()])

    def setModel(self, model_name: str) -> dict:
        """
        Sets the live2d model name and returns the matched model dictionary.

        Parameters:
            model_name (str): The name of the live2d model.

        Returns:
            dict: The matched model dictionary.

        Raises:
            None

        """
        self.live2d_model_name = model_name

        try:
            with open(self.modelDictPath, "r") as file:
                model_dict = json.load(file)
        except FileNotFoundError as file_e:
            print(f"Model dictionary file not found at {self.modelDictPath}.")
            raise file_e
        except json.JSONDecodeError as json_e:
            print(
                f"Error decoding JSON from model dictionary file at {self.modelDictPath}."
            )
            raise json_e
        except Exception as e:
            print(
                f"Error occurred while reading model dictionary file at {self.modelDictPath}."
            )
            raise e

        # Find the model in the model_dict
        matched_model = next(
            (model for model in model_dict if model["name"] == model_name), None
        )

        if matched_model is None:
            print(f"No model found for {model_name}. Exiting.")
            exit()

        if matched_model["url"].startswith("/"):
            matched_model["url"] = self.base_url + matched_model["url"]

        print(f"Model set to: {matched_model['name']}")
        print(f"URL set to: {matched_model['url']}")

        self.send_message_to_broadcast({"type": "set-model", "text": matched_model})
        return matched_model

    def setExpression(self, expression: str):
        """
        Sets the expression of the Live2D model.

        This method sends a message to the broadcast route with the expression to be set immediately.
        The expression is mapped to the corresponding text in the `emoMap` dictionary.

        Parameters:
        - expression (str): The expression to be set.

        Prints:
        - The expression being set to the console.
        """

        print(f">>>>>> setExpression ({self.emoMap[expression]}): {expression}")
        self.send_message_to_broadcast(
            {"type": "expression", "text": self.emoMap[expression]}
        )

    def startSpeaking(self):
        """
        Sends a signal to the live2D front-end: start speaking.

        Parameters:
            None

        Returns:
            None
        """
        self.send_message_to_broadcast({"type": "control", "text": "speaking-start"})

    def stopSpeaking(self):
        """
        Sends a signal to the live2D front-end: stop speaking.

        Parameters:
            None

        Returns:
            None
        """
        self.send_message_to_broadcast({"type": "control", "text": "speaking-stop"})

    def get_mic_audio(self):
        """
        Get microphone audio from the front end.

        Parameters:
            None

        Returns:
            np.array: The audio samples in Float32Array at sample rate 16000.
        """

        def on_message(ws, message):
            data = json.loads(message)
            if data.get("type") == "mic-audio":
                self.received_data_buffer = np.append(
                    self.received_data_buffer,
                    np.array(list(data.get("audio").values()), dtype=np.float32),
                )
                print(".", end="")
                # ws.close()
            if data.get("type") == "mic-audio-end":
                print("Received audio data end from front end.")
                ws.close()

        def on_error(ws, error):
            print("Error:", error)

        def on_close(ws, close_status_code, close_msg):
            print("### closed ###")

        def on_open(ws):
            print("Start waiting for audio data from front end...")

        ws = websocket.WebSocketApp(
            f"ws://{self.base_url.split('//')[1]}/server-ws",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.run_forever()
        # data in Float32Array of audio samples at sample rate 16000
        result = self.received_data_buffer
        self.received_data_buffer = np.array([])
        return result

    def send_text(self, text):
        """
        Sends a text message to the live2D front-end.

        Parameters:
            text (str): The text message to send.

        Returns:
            None
        """
        self.send_message_to_broadcast({"type": "full-text", "text": text})

    def send_expressions_str(self, str, send_delay=3):
        """
        Checks if the given string contains any expressions defined in the emoMap dictionary,
        and send the corresponding expressions one-by-one every 3 sec to the Live2D model.

        Parameters:
            str (str): The string to check for expressions.
            send_delay (int): The delay in seconds between sending each expression.

        Returns:
            None

        Raises:
            None
        """
        for key, value in self.emoMap.items():
            if f"[{key}]" in str.lower():
                # print(f">> [ ] <- add to exec queue: {key}, {value}")
                def new_task(num):
                    self.setExpression(num)
                    time.sleep(send_delay)

                self.task_queue.add_task(new_task(key))

    def get_expression_list(self, str):
        """
        Checks if the given string contains any expressions defined in the emoMap dictionary,
        and return a list of index of expressions found in the string.

        Parameters:
            str (str): The string to check for expressions.

        Returns:
            list: A list of the index of expressions found in the string.

        Raises:
            None
        """
        expression_list = []
        for key in self.emoMap.keys():
            if f"[{key}]" in str.lower():
                expression_list.append(self.emoMap[key])
        return expression_list

    def remove_expression_from_string(self, str):
        """
        Checks if the given string contains any expressions defined in the emoMap dictionary,
        and return a string without those expression keywords.

        Parameters:
            str (str): The string to check for expressions.

        Returns:
            str: The string without the expression keywords.

        Raises:
            None
        """
        lower_str = str.lower()

        for key in self.emoMap.keys():
            lower_key = f"[{key}]".lower()
            while lower_key in lower_str:
                start_index = lower_str.find(lower_key)
                end_index = start_index + len(lower_key)
                str = str[:start_index] + str[end_index:]
                lower_str = lower_str[:start_index] + lower_str[end_index:]
        return str

    def send_message_to_broadcast(self, message):
        """
        Sends a message to the broadcast route.

        This method constructs a URL by appending "/broadcast" to the base URL stored in `self.base_url`.
        It then serializes the `message` parameter into a JSON string using `json.dumps` and sends this
        payload as a JSON object within a POST request to the constructed URL. The response from the
        server is checked for success (response.ok), and a message is printed to the console indicating
        the status of the operation.

        Parameters:
        - message (dict): A dictionary containing the message to be sent. This dictionary is serialized
                        into a JSON string before being sent.

        Prints:
        - The status code of the response to the console.
        - A success message if the message was successfully sent to the broadcast route.
        """
        url = self.base_url + "/broadcast"

        payload = json.dumps(message)

        response = requests.post(url, json={"message": payload})


if __name__ == "__main__":

    live2d = Live2dController("shizuku-local")

    aud = live2d.get_mic_audio()

    from asr.faster_whisper_asr import VoiceRecognition

    text = VoiceRecognition().transcribe_np(aud)

    print(text)

    input("Press Enter to continue...")

    # with open("cache.txt", "w") as file:
    #     file.write(str(aud))

    print("done")

    print(aud)

    # print(live2d.getEmoMapKeyAsString())

    text = (
        "*joins hands and smiles* * [SmIrK]: HEHE, YOU THINK YOU CAN HANDLE THE TRUTH?"
    )
    print(text)
    # live2d.startSpeaking()
    print(live2d.remove_expression_from_string(text))
